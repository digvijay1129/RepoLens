"""Single planned-step execution through the controlled read-only tool registry."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.approvals import action_digest
from app.agents.memory import capture_tool_execution_memory, retrieve_relevant_memories
from app.agents.schemas import AgentTaskStatus
from app.agents.team import route_step_to_specialist
from app.agents.tool_calling import select_tool_call
from app.agents.tools import (
    AgentToolContext,
    AgentToolError,
    build_agent_tool_registry,
)
from app.models.agent_approval_request import AgentApprovalRequest
from app.models.agent_delegation import AgentDelegation
from app.models.agent_step import AgentStep
from app.models.agent_task import AgentTask
from app.models.agent_tool_execution import AgentToolExecution
from app.models.repository import Repository
from app.services.llm import LLMConfigurationError, LLMProviderError


class AgentStepNotFoundError(RuntimeError):
    """Raised when a planned step does not belong to the task owner."""


class AgentExecutionConflictError(RuntimeError):
    """Raised when the task, step, or dependency state disallows execution."""


def _serialize_execution(execution: AgentToolExecution) -> dict[str, Any]:
    return {
        "id": execution.id,
        "task_id": execution.task_id,
        "step_id": execution.step_id,
        "tool_name": execution.tool_name,
        "status": execution.status,
        "tool_input": execution.tool_input or {},
        "tool_output": execution.tool_output,
        "error_message": execution.error_message,
        "duration_ms": execution.duration_ms,
        "created_at": execution.created_at.isoformat() if execution.created_at else None,
        "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
    }



def _summarize_specialist_result(output: dict[str, Any]) -> str:
    """Build a bounded summary without copying source-code excerpts."""
    fields = [
        ("repository", output.get("repository")),
        ("file_path", output.get("file_path")),
        ("result_count", output.get("result_count")),
        ("indexed_file_count", output.get("indexed_file_count")),
        ("indexed_chunk_count", output.get("indexed_chunk_count")),
        ("returned_line_count", output.get("returned_line_count")),
        ("commit_sha", output.get("commit_sha")),
    ]
    parts = [f"{key}: {value}" for key, value in fields if value is not None]
    if not parts:
        parts.append("Read-only repository evidence collected; inspect the linked tool output.")
    return "; ".join(parts)[:1000]


def list_agent_tools(
    db: Session,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[dict[str, Any]]:
    task = db.scalar(
        select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user_id)
    )
    if task is None:
        raise AgentStepNotFoundError("Agent task was not found.")
    return build_agent_tool_registry().list_tools()


def list_tool_executions(
    db: Session,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[dict[str, Any]]:
    task = db.scalar(
        select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user_id)
    )
    if task is None:
        raise AgentStepNotFoundError("Agent task was not found.")
    executions = db.scalars(
        select(AgentToolExecution)
        .where(
            AgentToolExecution.task_id == task_id,
            AgentToolExecution.user_id == user_id,
        )
        .order_by(AgentToolExecution.created_at.asc(), AgentToolExecution.id.asc())
    ).all()
    return [_serialize_execution(execution) for execution in executions]


class AgentApprovalRequired(RuntimeError):
    """Signals that a proposed tool action was safely saved for owner approval."""

    def __init__(self, approval_id: uuid.UUID) -> None:
        self.approval_id = approval_id
        super().__init__("Human approval is required before this tool action can execute.")


async def execute_agent_step(
    db: Session,
    *,
    task_id: uuid.UUID,
    step_key: str,
    user_id: uuid.UUID,
    instruction: str | None = None,
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Select one read-only tool, optionally gate it on owner approval, then execute."""
    task = db.scalar(
        select(AgentTask)
        .where(AgentTask.id == task_id, AgentTask.user_id == user_id)
        .with_for_update()
    )
    if task is None:
        raise AgentStepNotFoundError("Agent task was not found.")
    if task.status not in {
        AgentTaskStatus.PLANNED.value,
        AgentTaskStatus.RUNNING.value,
    }:
        raise AgentExecutionConflictError("Only planned or running tasks can execute an individual step.")
    repository = db.scalar(
        select(Repository).where(
            Repository.id == task.repository_id,
            Repository.user_id == user_id,
        )
    )
    if repository is None:
        raise AgentStepNotFoundError("Saved repository was not found.")
    if (
        repository.indexing_status != "indexed"
        or not repository.indexed_commit_sha
        or repository.indexed_commit_sha != task.indexed_commit_sha
    ):
        raise AgentExecutionConflictError(
            "The repository snapshot has changed. Recreate the task against the current indexed commit."
        )

    step = db.scalar(
        select(AgentStep)
        .where(
            AgentStep.task_id == task.id,
            AgentStep.user_id == user_id,
            AgentStep.repository_id == repository.id,
            AgentStep.step_key == step_key,
        )
        .with_for_update()
    )
    if step is None:
        raise AgentStepNotFoundError("Planned step was not found.")
    if step.status not in {"pending", "failed"}:
        raise AgentExecutionConflictError(
            "This step is already running or completed and cannot be executed again."
        )

    if step.depends_on:
        step_rows = db.scalars(
            select(AgentStep).where(
                AgentStep.task_id == task.id,
                AgentStep.user_id == user_id,
                AgentStep.repository_id == repository.id,
            )
        ).all()
        status_by_key = {item.step_key: item.status for item in step_rows}
        incomplete = [
            dependency
            for dependency in step.depends_on
            if status_by_key.get(dependency) != "succeeded"
        ]
        if incomplete:
            raise AgentExecutionConflictError(
                "Complete prerequisite step(s) before executing this step: "
                + ", ".join(incomplete)
            )

    memory_query = " ".join(
        part for part in (
            task.goal,
            step.title,
            step.description,
            step.expected_output,
        ) if part
    )
    memories = retrieve_relevant_memories(
        db,
        repository_id=repository.id,
        user_id=user_id,
        query=memory_query,
        current_commit_sha=task.indexed_commit_sha,
        limit=6,
    )
    if memories:
        observations = list(observations or [])
        observations.append(
            {
                "step_key": "repository_memory",
                "step_title": "Retrieved repository memories (untrusted contextual data)",
                "tool_name": "repository_memory",
                "result": [
                    {
                        "memory_type": item["memory_type"],
                        "title": item["title"],
                        "content": item["content"],
                        "tags": item["tags"],
                        "source_refs": item["source_refs"],
                        "source_commit_sha": item["source_commit_sha"],
                        "snapshot_matches": item.get("snapshot_matches"),
                    }
                    for item in memories
                ],
            }
        )

    specialist = route_step_to_specialist(step)
    registry = build_agent_tool_registry()
    now = datetime.now(timezone.utc)
    approval = db.scalar(
        select(AgentApprovalRequest)
        .where(
            AgentApprovalRequest.task_id == task.id,
            AgentApprovalRequest.step_id == step.id,
            AgentApprovalRequest.user_id == user_id,
            AgentApprovalRequest.status == "approved",
        )
        .order_by(AgentApprovalRequest.requested_at.desc())
        .with_for_update()
    )

    approved_action = approval is not None
    if not approved_action and task.total_tool_calls >= task.max_tool_calls:
        raise AgentExecutionConflictError("The task has reached its maximum tool-call budget.")
    if approved_action:
        expires_at = approval.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            approval.status = "expired"
            approval.decision_comment = "Approval expired before the approved action was resumed."
            approval.decided_at = now
            task.status = AgentTaskStatus.FAILED.value
            task.latest_error = "The approved action expired before execution. Create a new task."
            task.execution_finished_at = now
            proposed = db.get(AgentToolExecution, approval.proposed_execution_id)
            delegation = db.get(AgentDelegation, approval.delegation_id)
            if proposed is not None:
                proposed.status = "failed"
                proposed.error_message = "Approval expired before execution."
                proposed.finished_at = now
            if delegation is not None:
                delegation.status = "cancelled"
                delegation.error_message = "Approval expired before execution."
                delegation.finished_at = now
            db.commit()
            raise AgentExecutionConflictError("The approved action expired before execution.")
        if approval.specialist_key != specialist.key:
            raise AgentExecutionConflictError("The approved specialist assignment no longer matches this plan step.")
        if action_digest(approval.tool_name, approval.tool_arguments or {}) != approval.action_hash:
            raise AgentExecutionConflictError("The approved action integrity check failed.")
        proposed = db.scalar(
            select(AgentToolExecution).where(
                AgentToolExecution.id == approval.proposed_execution_id,
                AgentToolExecution.task_id == task.id,
                AgentToolExecution.step_id == step.id,
                AgentToolExecution.user_id == user_id,
                AgentToolExecution.repository_id == repository.id,
                AgentToolExecution.status == "awaiting_approval",
            )
        )
        delegation = db.scalar(
            select(AgentDelegation).where(
                AgentDelegation.id == approval.delegation_id,
                AgentDelegation.task_id == task.id,
                AgentDelegation.step_id == step.id,
                AgentDelegation.user_id == user_id,
                AgentDelegation.repository_id == repository.id,
                AgentDelegation.status == "assigned",
            )
        )
        if proposed is None or delegation is None:
            raise AgentExecutionConflictError("The approved action no longer has a valid pending execution.")
        stored_input = proposed.tool_input or {}
        if (
            stored_input.get("arguments") != approval.tool_arguments
            or stored_input.get("specialist_key") != approval.specialist_key
            or stored_input.get("tool_name") != approval.tool_name
        ):
            raise AgentExecutionConflictError("The proposed action changed after approval.")
        try:
            definition = registry.get(approval.tool_name)
            normalized_arguments = definition.arguments_model.model_validate(
                approval.tool_arguments or {}
            ).model_dump(mode="json")
        except Exception as exc:
            raise AgentExecutionConflictError("The approved tool or arguments are no longer allowed.") from exc
        if normalized_arguments != approval.tool_arguments:
            raise AgentExecutionConflictError("The approved arguments are no longer in canonical form.")
        execution = proposed
        selected_name = approval.tool_name
        selected_arguments = approval.tool_arguments
        execution.status = "running"
        execution.error_message = None
        execution.finished_at = None
        delegation.status = "running"
        delegation.error_message = None
        delegation.finished_at = None
        step.status = "running"
        step.updated_at = now
        task.status = AgentTaskStatus.RUNNING.value
        task.updated_at = now
        db.commit()
        db.refresh(execution)
    else:
        attempt_number = int(
            db.scalar(
                select(func.count(AgentDelegation.id)).where(
                    AgentDelegation.task_id == task.id,
                    AgentDelegation.step_id == step.id,
                    AgentDelegation.user_id == user_id,
                )
            ) or 0
        ) + 1
        if attempt_number > 3:
            raise AgentExecutionConflictError(
                "This step has reached the maximum of three specialist delegation attempts."
            )
        delegation = AgentDelegation(
            task_id=task.id,
            step_id=step.id,
            user_id=user_id,
            repository_id=repository.id,
            specialist_key=specialist.key,
            specialist_name=specialist.display_name,
            mission=specialist.mission,
            status="running",
            attempt_number=attempt_number,
            assignment_context={
                "task_goal": task.goal[:1200],
                "step_key": step.step_key,
                "step_title": step.title,
                "expected_output": step.expected_output,
                "indexed_commit_sha": task.indexed_commit_sha,
            },
            started_at=now,
        )
        started = time.perf_counter()
        execution = AgentToolExecution(
            task_id=task.id,
            step_id=step.id,
            user_id=user_id,
            repository_id=repository.id,
            tool_name="tool_selection",
            status="running",
            tool_input={
                "step_key": step.step_key,
                "instruction": instruction or "",
                "specialist_key": specialist.key,
            },
        )
        step.status = "running"
        task.total_tool_calls += 1
        task.updated_at = now
        db.add(delegation)
        db.add(execution)
        db.commit()
        db.refresh(execution)
        db.refresh(delegation)

        try:
            selected = await select_tool_call(
                task,
                step,
                registry,
                instruction=instruction,
                observations=observations,
                specialist=specialist,
            )
            definition = registry.get(selected.name)
            normalized_arguments = definition.arguments_model.model_validate(
                selected.arguments
            ).model_dump(mode="json")
            execution.provider_call_id = selected.call_id
            execution.tool_name = definition.name
            execution.tool_input = {
                "step_key": step.step_key,
                "tool_name": definition.name,
                "arguments": normalized_arguments,
                "instruction": instruction or "",
                "specialist_key": specialist.key,
                "specialist_name": specialist.display_name,
            }
            db.flush()
            db.commit()
            db.refresh(execution)

            if task.approval_mode == "approve_each":
                approval = AgentApprovalRequest(
                    task_id=task.id,
                    step_id=step.id,
                    user_id=user_id,
                    repository_id=repository.id,
                    delegation_id=delegation.id,
                    proposed_execution_id=execution.id,
                    approval_mode="approve_each",
                    tool_name=definition.name,
                    tool_arguments=normalized_arguments,
                    provider_call_id=selected.call_id,
                    action_hash=action_digest(definition.name, normalized_arguments),
                    specialist_key=specialist.key,
                    policy_reason=(
                        "This task requires owner approval for every proposed tool call. "
                        "The tool is registered as read-only and will not run until approved."
                    ),
                    status="pending",
                    requested_at=now,
                    expires_at=now + timedelta(minutes=15),
                )
                execution.status = "awaiting_approval"
                execution.error_message = "Waiting for owner approval; the tool handler has not been invoked."
                execution.duration_ms = max(0, int((time.perf_counter() - started) * 1000))
                execution.finished_at = now
                delegation.status = "assigned"
                delegation.finished_at = None
                step.status = "pending"
                task.status = AgentTaskStatus.AWAITING_APPROVAL.value
                task.latest_error = "A proposed read-only tool action is waiting for owner approval."
                task.updated_at = now
                db.add(approval)
                db.commit()
                db.refresh(approval)
                raise AgentApprovalRequired(approval.id)

            selected_name = definition.name
            selected_arguments = normalized_arguments
            provider_call_id = selected.call_id
        except AgentApprovalRequired:
            raise
        except (AgentToolError, LLMConfigurationError, LLMProviderError) as exc:
            db.rollback()
            execution = db.get(AgentToolExecution, execution.id)
            step = db.get(AgentStep, step.id)
            delegation = db.get(AgentDelegation, delegation.id)
            if execution is not None:
                execution.status = "failed"
                execution.error_message = str(exc)[:1000]
                execution.duration_ms = max(0, int((time.perf_counter() - started) * 1000))
                execution.finished_at = datetime.now(timezone.utc)
            if step is not None:
                step.status = "failed"
                step.updated_at = datetime.now(timezone.utc)
            if delegation is not None:
                delegation.status = "failed"
                delegation.error_message = str(exc)[:1000]
                delegation.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise
        except Exception as exc:
            db.rollback()
            execution = db.get(AgentToolExecution, execution.id)
            step = db.get(AgentStep, step.id)
            delegation = db.get(AgentDelegation, delegation.id)
            if execution is not None:
                execution.status = "failed"
                execution.error_message = "Tool selection failed unexpectedly."
                execution.duration_ms = max(0, int((time.perf_counter() - started) * 1000))
                execution.finished_at = datetime.now(timezone.utc)
            if step is not None:
                step.status = "failed"
                step.updated_at = datetime.now(timezone.utc)
            if delegation is not None:
                delegation.status = "failed"
                delegation.error_message = "Specialist tool selection failed unexpectedly."
                delegation.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise AgentToolError("Tool selection failed unexpectedly.") from exc

    started = time.perf_counter()
    try:
        output = await registry.execute(
            selected_name,
            selected_arguments,
            AgentToolContext(db=db, repository=repository, user_id=user_id),
        )
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        execution.status = "succeeded"
        execution.tool_input = {
            **(execution.tool_input or {}),
            "tool_name": selected_name,
            "arguments": selected_arguments,
            "specialist_key": specialist.key,
            "specialist_name": specialist.display_name,
        }
        execution.tool_output = output
        execution.error_message = None
        execution.duration_ms = duration_ms
        execution.finished_at = datetime.now(timezone.utc)
        delegation.source_execution_id = execution.id
        delegation.status = "succeeded"
        delegation.result_summary = _summarize_specialist_result(output)
        delegation.error_message = None
        delegation.finished_at = datetime.now(timezone.utc)
        step.status = "succeeded"
        step.updated_at = datetime.now(timezone.utc)
        if approved_action and approval is not None:
            approval.status = "executed"
            approval.executed_execution_id = execution.id
            approval.decision_comment = (
                (approval.decision_comment + " | ") if approval.decision_comment else ""
            ) + "The exact approved action was executed."
        db.commit()
        db.refresh(execution)
        try:
            capture_tool_execution_memory(
                db,
                task_id=task.id,
                user_id=user_id,
                execution_id=execution.id,
            )
        except Exception:
            db.rollback()
        return _serialize_execution(execution)
    except (AgentToolError, LLMConfigurationError, LLMProviderError) as exc:
        db.rollback()
        execution = db.get(AgentToolExecution, execution.id)
        step = db.get(AgentStep, step.id)
        delegation = db.get(AgentDelegation, delegation.id)
        if execution is not None:
            execution.status = "failed"
            execution.error_message = str(exc)[:1000]
            execution.duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            execution.finished_at = datetime.now(timezone.utc)
        if step is not None:
            step.status = "failed"
            step.updated_at = datetime.now(timezone.utc)
        if delegation is not None:
            delegation.status = "failed"
            delegation.error_message = str(exc)[:1000]
            delegation.finished_at = datetime.now(timezone.utc)
        if approved_action and approval is not None:
            approval = db.get(AgentApprovalRequest, approval.id)
            if approval is not None:
                approval.status = "cancelled"
                approval.decision_comment = "Approved action execution failed; the approval cannot be reused."
        db.commit()
        raise
    except Exception as exc:
        db.rollback()
        execution = db.get(AgentToolExecution, execution.id)
        step = db.get(AgentStep, step.id)
        delegation = db.get(AgentDelegation, delegation.id)
        if execution is not None:
            execution.status = "failed"
            execution.error_message = "Tool execution failed unexpectedly."
            execution.duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            execution.finished_at = datetime.now(timezone.utc)
        if step is not None:
            step.status = "failed"
            step.updated_at = datetime.now(timezone.utc)
        if delegation is not None:
            delegation.status = "failed"
            delegation.error_message = "Specialist execution failed unexpectedly."
            delegation.finished_at = datetime.now(timezone.utc)
        if approved_action and approval is not None:
            approval = db.get(AgentApprovalRequest, approval.id)
            if approval is not None:
                approval.status = "cancelled"
                approval.decision_comment = "Approved action execution failed; the approval cannot be reused."
        db.commit()
        raise AgentToolError("Tool execution failed unexpectedly.") from exc
