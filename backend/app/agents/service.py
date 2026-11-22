"""Persistence service for creating and inspecting Phase 1 agent tasks."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import AgentOrchestrator
from app.agents.schemas import AgentTaskStatus
from app.agents.state import AgentExecutionState
from app.models.agent_task import AgentTask
from app.models.agent_plan import AgentPlan
from app.models.agent_step import AgentStep
from app.models.repository import Repository


class AgentTaskNotFoundError(RuntimeError):
    """Raised when a task does not belong to the current user."""


class AgentRepositoryNotReadyError(RuntimeError):
    """Raised when the selected repository is not ready for agent work."""


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else datetime.now(timezone.utc).isoformat()


def serialize_step(step: AgentStep) -> dict[str, Any]:
    return {
        "id": str(step.id),
        "step_key": step.step_key,
        "position": step.position,
        "title": step.title,
        "description": step.description,
        "rationale": step.rationale,
        "expected_output": step.expected_output,
        "suggested_tool": step.suggested_tool,
        "depends_on": step.depends_on or [],
        "status": step.status,
    }


def serialize_task(task: AgentTask, *, include_plan: bool = True) -> dict[str, Any]:
    plan = task.plan
    return {
        "id": task.id,
        "repository_id": task.repository_id,
        "goal": task.goal,
        "status": task.status,
        "max_steps": task.max_steps,
        "created_at": _iso(task.created_at),
        "updated_at": _iso(task.updated_at),
        "latest_error": task.latest_error,
        "max_tool_calls": task.max_tool_calls,
        "max_retries_per_step": task.max_retries_per_step,
        "total_tool_calls": task.total_tool_calls,
        "total_retries": task.total_retries,
        "final_result": task.final_result,
        "execution_started_at": (
            task.execution_started_at.isoformat() if task.execution_started_at else None
        ),
        "execution_finished_at": (
            task.execution_finished_at.isoformat() if task.execution_finished_at else None
        ),
        "plan": (
            {
                "summary": plan.summary,
                "completion_criteria": plan.completion_criteria,
                "assumptions": plan.assumptions,
                "planner_provider": plan.planner_provider,
                "planner_model": plan.planner_model,
                "version": plan.version,
            }
            if include_plan and plan
            else None
        ),
        "steps": [serialize_step(step) for step in sorted(task.steps, key=lambda item: item.position)],
    }


async def create_agent_task(
    db: Session,
    *,
    user_id: uuid.UUID,
    repository: Repository,
    goal: str,
    max_steps: int,
) -> AgentTask:
    """Persist a queued task and a validated plan; no tool execution occurs."""
    if repository.user_id != user_id:
        raise AgentRepositoryNotReadyError("Saved repository was not found.")
    if repository.indexing_status != "indexed" or not repository.indexed_commit_sha:
        raise AgentRepositoryNotReadyError("Index the repository before creating an agent task.")

    task = AgentTask(
        user_id=user_id,
        repository_id=repository.id,
        indexed_commit_sha=repository.indexed_commit_sha,
        goal=goal.strip(),
        max_steps=max_steps,
        status=AgentTaskStatus.PLANNING.value,
    )
    db.add(task)
    db.flush()
    try:
        planning = await AgentOrchestrator().plan_goal(goal.strip(), max_steps=max_steps)
        proposal = planning.proposal
        plan = AgentPlan(
            task_id=task.id,
            user_id=user_id,
            repository_id=repository.id,
            version=1,
            summary=proposal.summary,
            completion_criteria=proposal.completion_criteria,
            assumptions=proposal.assumptions,
            planner_provider=planning.provider,
            planner_model=planning.model,
        )
        db.add(plan)
        db.flush()
        for position, step in enumerate(proposal.steps, start=1):
            db.add(
                AgentStep(
                    task_id=task.id,
                    plan_id=plan.id,
                    user_id=user_id,
                    repository_id=repository.id,
                    position=position,
                    step_key=step.step_key,
                    title=step.title,
                    description=step.description,
                    rationale=step.rationale,
                    expected_output=step.expected_output,
                    suggested_tool=step.suggested_tool,
                    depends_on=step.depends_on,
                    status="pending",
                )
            )
        task.status = AgentTaskStatus.PLANNED.value
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)
        return task
    except Exception:
        db.rollback()
        raise


def get_agent_task(
    db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID
) -> AgentTask:
    task = db.scalar(
        select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user_id)
    )
    if task is None:
        raise AgentTaskNotFoundError("Agent task was not found.")
    return task


def list_agent_tasks(
    db: Session,
    *,
    user_id: uuid.UUID,
    repository_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[AgentTask]:
    statement = select(AgentTask).where(AgentTask.user_id == user_id)
    if repository_id is not None:
        statement = statement.where(AgentTask.repository_id == repository_id)
    return list(
        db.scalars(
            statement.order_by(AgentTask.created_at.desc()).limit(max(1, min(limit, 50)))
        ).all()
    )


def cancel_agent_task(db: Session, *, task_id: uuid.UUID, user_id: uuid.UUID) -> AgentTask:
    task = get_agent_task(db, task_id=task_id, user_id=user_id)
    state = AgentExecutionState(
        task_id=task.id,
        user_id=task.user_id,
        repository_id=task.repository_id,
        indexed_commit_sha=task.indexed_commit_sha,
        status=AgentTaskStatus(task.status),
    )
    try:
        state.transition_to(AgentTaskStatus.CANCELLED)
    except ValueError as exc:
        raise ValueError("Only non-terminal agent tasks can be cancelled.") from exc
    task.status = state.status.value
    task.updated_at = datetime.now(timezone.utc)
    task.execution_finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task
