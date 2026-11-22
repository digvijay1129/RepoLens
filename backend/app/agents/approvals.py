"""One-time, owner-scoped human decisions for proposed agent tool actions."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.tools import AgentToolError, build_agent_tool_registry
from app.models.agent_approval_request import AgentApprovalRequest
from app.models.agent_delegation import AgentDelegation
from app.models.agent_step import AgentStep
from app.models.agent_task import AgentTask
from app.models.agent_tool_execution import AgentToolExecution
from app.models.repository import Repository


APPROVAL_TTL_MINUTES = 15


class AgentApprovalNotFoundError(RuntimeError):
    """An approval request is not visible to the authenticated user."""


class AgentApprovalConflictError(RuntimeError):
    """The approval request is expired, stale or no longer actionable."""


def action_digest(tool_name: str, arguments: dict[str, Any]) -> str:
    """Hash the exact normalized action that was presented for approval."""
    canonical = json.dumps(
        {"tool_name": tool_name, "arguments": arguments},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def serialize_approval(approval: AgentApprovalRequest) -> dict[str, Any]:
    return {
        "id": approval.id,
        "task_id": approval.task_id,
        "step_id": approval.step_id,
        "delegation_id": approval.delegation_id,
        "proposed_execution_id": approval.proposed_execution_id,
        "executed_execution_id": approval.executed_execution_id,
        "approval_mode": approval.approval_mode,
        "tool_name": approval.tool_name,
        "tool_arguments": approval.tool_arguments or {},
        "provider_call_id": approval.provider_call_id,
        "action_hash": approval.action_hash,
        "specialist_key": approval.specialist_key,
        "policy_reason": approval.policy_reason,
        "status": approval.status,
        "requested_at": approval.requested_at.isoformat() if approval.requested_at else None,
        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
        "decided_by_user_id": approval.decided_by_user_id,
        "decision_comment": approval.decision_comment,
    }


def _owned_approval(
    db: Session,
    *,
    approval_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AgentApprovalRequest:
    approval = db.scalar(
        select(AgentApprovalRequest)
        .where(
            AgentApprovalRequest.id == approval_id,
            AgentApprovalRequest.user_id == user_id,
        )
        .with_for_update()
    )
    if approval is None:
        raise AgentApprovalNotFoundError("Approval request was not found.")
    return approval


def list_task_approvals(
    db: Session,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 50,
) -> list[dict[str, Any]]:
    task = db.scalar(
        select(AgentTask).where(
            AgentTask.id == task_id,
            AgentTask.user_id == user_id,
        )
    )
    if task is None:
        raise AgentApprovalNotFoundError("Agent task was not found.")
    requests = db.scalars(
        select(AgentApprovalRequest)
        .where(
            AgentApprovalRequest.task_id == task_id,
            AgentApprovalRequest.user_id == user_id,
        )
        .order_by(AgentApprovalRequest.requested_at.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [serialize_approval(item) for item in requests]




def _invalidate_approval(
    db: Session,
    approval: AgentApprovalRequest,
    task: AgentTask,
    reason: str,
) -> None:
    now = datetime.now(timezone.utc)
    approval.status = "expired"
    approval.decided_at = now
    approval.decision_comment = reason[:1000]
    task.status = "failed"
    task.latest_error = reason[:1000]
    task.execution_finished_at = now
    if approval.proposed_execution_id:
        proposed = db.get(AgentToolExecution, approval.proposed_execution_id)
        if proposed is not None and proposed.status == "awaiting_approval":
            proposed.status = "failed"
            proposed.error_message = reason[:1000]
            proposed.finished_at = now
    if approval.delegation_id:
        delegation = db.get(AgentDelegation, approval.delegation_id)
        if delegation is not None and delegation.status in {"assigned", "running"}:
            delegation.status = "cancelled"
            delegation.error_message = reason[:1000]
            delegation.finished_at = now
    db.commit()

def _validate_proposal_still_safe(
    db: Session,
    approval: AgentApprovalRequest,
    task: AgentTask,
) -> None:
    repository = db.scalar(
        select(Repository).where(
            Repository.id == approval.repository_id,
            Repository.user_id == approval.user_id,
        )
    )
    if (
        repository is None
        or repository.indexing_status != "indexed"
        or repository.indexed_commit_sha != task.indexed_commit_sha
    ):
        reason = (
            "The indexed repository snapshot changed. This approval was invalidated and the task was stopped."
        )
        _invalidate_approval(db, approval, task, reason)
        raise AgentApprovalConflictError(reason)
    if approval.status != "pending":
        raise AgentApprovalConflictError(
            f"This approval request is already {approval.status} and cannot be decided again."
        )
    if approval.expires_at is None:
        raise AgentApprovalConflictError("The approval request has no valid expiry.")
    expires_at = approval.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        reason = "The approval request expired before a decision. The task has been stopped safely."
        _invalidate_approval(db, approval, task, reason)
        raise AgentApprovalConflictError(reason)

    if task.status != "awaiting_approval":
        raise AgentApprovalConflictError("The task is no longer waiting for this approval.")

    if not approval.proposed_execution_id or not approval.delegation_id:
        raise AgentApprovalConflictError("The approval record is missing its proposed execution.")

    proposed = db.scalar(
        select(AgentToolExecution).where(
            AgentToolExecution.id == approval.proposed_execution_id,
            AgentToolExecution.task_id == task.id,
            AgentToolExecution.step_id == approval.step_id,
            AgentToolExecution.user_id == approval.user_id,
            AgentToolExecution.repository_id == approval.repository_id,
            AgentToolExecution.status == "awaiting_approval",
        )
    )
    if proposed is None:
        raise AgentApprovalConflictError("The proposed action is no longer awaiting approval.")

    stored_input = proposed.tool_input or {}
    if (
        stored_input.get("arguments") != approval.tool_arguments
        or stored_input.get("specialist_key") != approval.specialist_key
        or stored_input.get("tool_name") != approval.tool_name
    ):
        reason = "The proposed action changed after approval was requested. The request was invalidated."
        _invalidate_approval(db, approval, task, reason)
        raise AgentApprovalConflictError(reason)

    if action_digest(approval.tool_name, approval.tool_arguments or {}) != approval.action_hash:
        reason = "The approved action integrity check failed. The request was invalidated."
        _invalidate_approval(db, approval, task, reason)
        raise AgentApprovalConflictError(reason)

    try:
        definition = build_agent_tool_registry().get(approval.tool_name)
        definition.arguments_model.model_validate(approval.tool_arguments or {})
    except (AgentToolError, ValueError) as exc:
        raise AgentApprovalConflictError("The proposed tool or arguments are no longer permitted.") from exc


def approve_action(
    db: Session,
    *,
    approval_id: uuid.UUID,
    user_id: uuid.UUID,
    comment: str | None = None,
) -> dict[str, Any]:
    approval = _owned_approval(db, approval_id=approval_id, user_id=user_id)
    task = db.scalar(
        select(AgentTask).where(
            AgentTask.id == approval.task_id,
            AgentTask.user_id == user_id,
        ).with_for_update()
    )
    if task is None:
        raise AgentApprovalNotFoundError("Agent task was not found.")
    _validate_proposal_still_safe(db, approval, task)
    approval.status = "approved"
    approval.decided_by_user_id = user_id
    approval.decided_at = datetime.now(timezone.utc)
    approval.decision_comment = comment.strip()[:1000] if comment and comment.strip() else None
    db.commit()
    db.refresh(approval)
    return serialize_approval(approval)


def deny_action(
    db: Session,
    *,
    approval_id: uuid.UUID,
    user_id: uuid.UUID,
    comment: str | None = None,
) -> dict[str, Any]:
    approval = _owned_approval(db, approval_id=approval_id, user_id=user_id)
    task = db.scalar(
        select(AgentTask).where(
            AgentTask.id == approval.task_id,
            AgentTask.user_id == user_id,
        ).with_for_update()
    )
    if task is None:
        raise AgentApprovalNotFoundError("Agent task was not found.")
    if approval.status != "pending":
        raise AgentApprovalConflictError(
            f"This approval request is already {approval.status} and cannot be denied."
        )
    expires_at = approval.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        reason = "The approval request expired before a decision. The task has been stopped safely."
        _invalidate_approval(db, approval, task, reason)
        raise AgentApprovalConflictError(reason)
    now = datetime.now(timezone.utc)
    approval.status = "denied"
    approval.decided_by_user_id = user_id
    approval.decided_at = now
    approval.decision_comment = comment.strip()[:1000] if comment and comment.strip() else "Denied by repository owner."
    task.status = "failed"
    task.latest_error = "The repository owner denied a proposed tool action. The task was stopped."
    task.execution_finished_at = now
    if approval.delegation_id:
        delegation = db.get(AgentDelegation, approval.delegation_id)
        if delegation is not None:
            delegation.status = "cancelled"
            delegation.error_message = "The repository owner denied the proposed action."
            delegation.finished_at = now
    if approval.proposed_execution_id:
        proposed = db.get(AgentToolExecution, approval.proposed_execution_id)
        if proposed is not None:
            proposed.status = "failed"
            proposed.error_message = "The repository owner denied this action before execution."
            proposed.finished_at = now
    db.commit()
    db.refresh(approval)
    return serialize_approval(approval)


def cancel_pending_approvals(
    db: Session,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Cancel outstanding approval requests in the same task-cancellation transaction."""
    now = datetime.now(timezone.utc)
    pending = db.scalars(
        select(AgentApprovalRequest).where(
            AgentApprovalRequest.task_id == task_id,
            AgentApprovalRequest.user_id == user_id,
            AgentApprovalRequest.status.in_({"pending", "approved"}),
            AgentApprovalRequest.executed_execution_id.is_(None),
        )
    ).all()
    for approval in pending:
        approval.status = "cancelled"
        approval.decided_by_user_id = user_id
        approval.decided_at = now
        approval.decision_comment = "Cancelled with the parent agent task."
        if approval.proposed_execution_id:
            proposed = db.get(AgentToolExecution, approval.proposed_execution_id)
            if proposed is not None and proposed.status == "awaiting_approval":
                proposed.status = "failed"
                proposed.error_message = "The parent agent task was cancelled."
                proposed.finished_at = now
        if approval.delegation_id:
            delegation = db.get(AgentDelegation, approval.delegation_id)
            if delegation is not None and delegation.status == "assigned":
                delegation.status = "cancelled"
                delegation.error_message = "The parent agent task was cancelled."
                delegation.finished_at = now
