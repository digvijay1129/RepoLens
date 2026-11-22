"""Owner-scoped team views and specialist delegation history."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.team import COORDINATOR_PROMPT, SPECIALISTS, summarize_team_assignments
from app.models.agent_delegation import AgentDelegation
from app.models.agent_step import AgentStep
from app.models.agent_task import AgentTask


class AgentTeamNotFoundError(RuntimeError):
    """Raised when a task team is not visible to the authenticated owner."""


def serialize_delegation(delegation: AgentDelegation) -> dict[str, Any]:
    return {
        "id": str(delegation.id),
        "task_id": str(delegation.task_id),
        "step_id": str(delegation.step_id),
        "source_execution_id": (
            str(delegation.source_execution_id) if delegation.source_execution_id else None
        ),
        "specialist_key": delegation.specialist_key,
        "specialist_name": delegation.specialist_name,
        "mission": delegation.mission,
        "status": delegation.status,
        "attempt_number": delegation.attempt_number,
        "assignment_context": delegation.assignment_context or {},
        "result_summary": delegation.result_summary,
        "error_message": delegation.error_message,
        "created_at": delegation.created_at.isoformat() if delegation.created_at else None,
        "started_at": delegation.started_at.isoformat() if delegation.started_at else None,
        "finished_at": delegation.finished_at.isoformat() if delegation.finished_at else None,
    }


def _owned_task(db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> AgentTask:
    task = db.scalar(
        select(AgentTask).where(
            AgentTask.id == task_id,
            AgentTask.user_id == user_id,
        )
    )
    if task is None:
        raise AgentTeamNotFoundError("Agent task was not found.")
    return task


def list_task_delegations(
    db: Session,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[dict[str, Any]]:
    _owned_task(db, task_id=task_id, user_id=user_id)
    records = db.scalars(
        select(AgentDelegation)
        .where(
            AgentDelegation.task_id == task_id,
            AgentDelegation.user_id == user_id,
        )
        .order_by(AgentDelegation.created_at.asc(), AgentDelegation.attempt_number.asc())
    ).all()
    return [serialize_delegation(record) for record in records]


def get_task_team(
    db: Session,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    task = _owned_task(db, task_id=task_id, user_id=user_id)
    steps = db.scalars(
        select(AgentStep)
        .where(
            AgentStep.task_id == task_id,
            AgentStep.user_id == user_id,
            AgentStep.repository_id == task.repository_id,
        )
        .order_by(AgentStep.position.asc())
    ).all()
    records = db.scalars(
        select(AgentDelegation)
        .where(
            AgentDelegation.task_id == task_id,
            AgentDelegation.user_id == user_id,
        )
        .order_by(AgentDelegation.created_at.asc(), AgentDelegation.attempt_number.asc())
    ).all()
    assignment_by_step = {
        assignment["step_key"]: assignment
        for assignment in summarize_team_assignments(steps)
    }
    records_by_step: dict[str, list[AgentDelegation]] = {}
    step_key_by_id = {step.id: step.step_key for step in steps}
    for record in records:
        step_key = step_key_by_id.get(record.step_id)
        if step_key:
            records_by_step.setdefault(step_key, []).append(record)

    specialist_items = []
    for key, specialist in SPECIALISTS.items():
        specialist_records = [item for item in records if item.specialist_key == key]
        specialist_items.append(
            {
                "key": specialist.key,
                "name": specialist.display_name,
                "mission": specialist.mission,
                "capabilities": list(specialist.capability_tags),
                "assigned_steps": len({
                    step_key_by_id[item.step_id]
                    for item in specialist_records
                    if item.step_id in step_key_by_id
                }),
                "completed_delegations": sum(item.status == "succeeded" for item in specialist_records),
                "failed_delegations": sum(item.status == "failed" for item in specialist_records),
            }
        )

    step_items = []
    for step in steps:
        assignment = assignment_by_step[step.step_key]
        history = records_by_step.get(step.step_key, [])
        latest = history[-1] if history else None
        step_items.append(
            {
                **assignment,
                "step_status": step.status,
                "delegation_count": len(history),
                "latest_delegation": serialize_delegation(latest) if latest else None,
            }
        )

    return {
        "task_id": str(task.id),
        "repository_id": str(task.repository_id),
        "indexed_commit_sha": task.indexed_commit_sha,
        "task_status": task.status,
        "coordinator": {
            "key": "coordinator",
            "name": "Main Coordinator Agent",
            "mission": "Route plan steps to specialists, enforce shared execution boundaries, and consolidate their evidence-backed findings.",
            "policy": COORDINATOR_PROMPT,
        },
        "specialists": specialist_items,
        "step_assignments": step_items,
        "delegation_count": len(records),
        "delegations": [serialize_delegation(record) for record in records],
    }
