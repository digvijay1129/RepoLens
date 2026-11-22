"""Bounded, resumable Plan → Act → Observe → Decide execution engine."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.execution import (
    AgentExecutionConflictError,
    AgentStepNotFoundError,
    execute_agent_step,
)
from app.agents.schemas import AgentTaskStatus
from app.agents.service import serialize_task
from app.models.agent_step import AgentStep
from app.models.agent_task import AgentTask
from app.models.agent_tool_execution import AgentToolExecution
from app.models.repository import Repository
from app.services.llm import LLMConfigurationError


class AgentRunNotFoundError(RuntimeError):
    """Raised when a task is not visible to the authenticated user."""


class AgentRunConflictError(RuntimeError):
    """Raised when task status or repository snapshot prevents a run."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _step_failed_attempts(db: Session, *, task_id: uuid.UUID, step_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count(AgentToolExecution.id)).where(
                AgentToolExecution.task_id == task_id,
                AgentToolExecution.step_id == step_id,
                AgentToolExecution.status == "failed",
            )
        )
        or 0
    )


def _successful_observations(db: Session, task_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(AgentToolExecution, AgentStep)
        .join(AgentStep, AgentStep.id == AgentToolExecution.step_id)
        .where(
            AgentToolExecution.task_id == task_id,
            AgentToolExecution.status == "succeeded",
        )
        .order_by(AgentToolExecution.created_at.asc(), AgentToolExecution.id.asc())
    ).all()
    observations: list[dict[str, Any]] = []
    for execution, step in rows[-6:]:
        observations.append(
            {
                "step_key": step.step_key,
                "step_title": step.title,
                "tool_name": execution.tool_name,
                "result": execution.tool_output,
            }
        )
    return observations


def _pause_task(db: Session, task: AgentTask, reason: str) -> dict[str, Any]:
    task.status = AgentTaskStatus.PAUSED.value
    task.latest_error = reason[:1000]
    task.execution_finished_at = _utcnow()
    task.updated_at = _utcnow()
    db.commit()
    db.refresh(task)
    return serialize_task(task)


def _fail_task(db: Session, task: AgentTask, reason: str) -> dict[str, Any]:
    task.status = AgentTaskStatus.FAILED.value
    task.latest_error = reason[:1000]
    task.execution_finished_at = _utcnow()
    task.updated_at = _utcnow()
    db.commit()
    db.refresh(task)
    return serialize_task(task)


def _complete_task(db: Session, task: AgentTask, steps: list[AgentStep]) -> dict[str, Any]:
    plan = task.plan
    executions = db.execute(
        select(AgentToolExecution, AgentStep)
        .join(AgentStep, AgentStep.id == AgentToolExecution.step_id)
        .where(
            AgentToolExecution.task_id == task.id,
            AgentToolExecution.status == "succeeded",
        )
        .order_by(AgentStep.position.asc(), AgentToolExecution.created_at.desc())
    ).all()
    latest_by_step: dict[str, dict[str, Any]] = {}
    for execution, step in executions:
        if step.step_key not in latest_by_step:
            latest_by_step[step.step_key] = {
                "step_key": step.step_key,
                "title": step.title,
                "tool_name": execution.tool_name,
                "result": execution.tool_output,
            }

    task.final_result = {
        "goal": task.goal,
        "summary": plan.summary if plan else "The planned repository task completed.",
        "completion_criteria": plan.completion_criteria if plan else [],
        "completed_steps": [
            latest_by_step[step.step_key]
            for step in sorted(steps, key=lambda item: item.position)
            if step.step_key in latest_by_step
        ],
        "execution": {
            "status": "completed",
            "tool_calls": task.total_tool_calls,
            "retries": task.total_retries,
            "indexed_commit_sha": task.indexed_commit_sha,
        },
    }
    task.status = AgentTaskStatus.COMPLETED.value
    task.latest_error = None
    task.execution_finished_at = _utcnow()
    task.updated_at = _utcnow()
    db.commit()
    db.refresh(task)
    return serialize_task(task)


async def run_agent_task(
    db: Session,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
    max_tool_calls: int | None = None,
    max_retries_per_step: int = 1,
    max_runtime_seconds: int = 90,
) -> dict[str, Any]:
    """Run ready plan steps until complete, cancelled, failed, or safely paused.

    Each tool call and step result commits independently. A resumed task therefore
    skips successful steps and continues with the first dependency-ready step.
    """
    task = db.scalar(
        select(AgentTask)
        .where(AgentTask.id == task_id, AgentTask.user_id == user_id)
        .with_for_update()
    )
    if task is None:
        raise AgentRunNotFoundError("Agent task was not found.")
    if task.status not in {
        AgentTaskStatus.PLANNED.value,
        AgentTaskStatus.PAUSED.value,
        AgentTaskStatus.RUNNING.value,
    }:
        raise AgentRunConflictError("Only planned, paused, or interrupted tasks can be started or resumed.")

    if task.status == AgentTaskStatus.RUNNING.value:
        last_update = task.updated_at
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)
        if (_utcnow() - last_update).total_seconds() <= 240:
            raise AgentRunConflictError("This agent task already has an active run.")
        # A process can stop after persisting 'running'. Mark its unfinished call
        # and step as failed so a retry can safely re-read the immutable snapshot.
        interrupted_calls = db.scalars(
            select(AgentToolExecution).where(
                AgentToolExecution.task_id == task.id,
                AgentToolExecution.user_id == user_id,
                AgentToolExecution.status == "running",
            )
        ).all()
        for call in interrupted_calls:
            call.status = "failed"
            call.error_message = "Execution was interrupted before the tool result was committed."
            call.finished_at = _utcnow()
        interrupted_steps = db.scalars(
            select(AgentStep).where(
                AgentStep.task_id == task.id,
                AgentStep.user_id == user_id,
                AgentStep.status == "running",
            )
        ).all()
        for interrupted_step in interrupted_steps:
            interrupted_step.status = "failed"
            interrupted_step.updated_at = _utcnow()

    repository = db.scalar(
        select(Repository).where(
            Repository.id == task.repository_id,
            Repository.user_id == user_id,
        )
    )
    if repository is None:
        raise AgentRunNotFoundError("Saved repository was not found.")
    if (
        repository.indexing_status != "indexed"
        or repository.indexed_commit_sha != task.indexed_commit_sha
    ):
        raise AgentRunConflictError(
            "The repository snapshot changed. Create a new plan against the current indexed commit."
        )

    if max_tool_calls is not None:
        task.max_tool_calls = max_tool_calls
    task.max_retries_per_step = max_retries_per_step
    task.status = AgentTaskStatus.RUNNING.value
    task.latest_error = None
    task.final_result = None
    task.execution_finished_at = None
    if task.execution_started_at is None:
        task.execution_started_at = _utcnow()
    task.updated_at = _utcnow()
    db.commit()
    db.refresh(task)

    run_started = time.monotonic()
    while True:
        db.refresh(task)
        if task.status == AgentTaskStatus.CANCELLED.value:
            return serialize_task(task)
        if task.status != AgentTaskStatus.RUNNING.value:
            return serialize_task(task)

        steps = db.scalars(
            select(AgentStep)
            .where(
                AgentStep.task_id == task.id,
                AgentStep.user_id == user_id,
                AgentStep.repository_id == repository.id,
            )
            .order_by(AgentStep.position.asc())
        ).all()
        if not steps:
            return _fail_task(db, task, "The task has no persisted plan steps.")

        if all(step.status == "succeeded" for step in steps):
            return _complete_task(db, task, steps)

        if time.monotonic() - run_started >= max_runtime_seconds:
            return _pause_task(db, task, "Run-time budget reached. Resume the task to continue.")
        if task.total_tool_calls >= task.max_tool_calls:
            return _pause_task(db, task, "Tool-call budget reached. Increase the budget and resume to continue.")

        status_by_key = {step.step_key: step.status for step in steps}
        ready_step = next(
            (
                step
                for step in steps
                if step.status in {"pending", "failed"}
                and all(status_by_key.get(dependency) == "succeeded" for dependency in step.depends_on)
            ),
            None,
        )
        if ready_step is None:
            blocked = [
                step.step_key
                for step in steps
                if step.status not in {"succeeded", "skipped"}
            ]
            return _fail_task(
                db,
                task,
                "No dependency-ready step remains. Blocked or invalid steps: " + ", ".join(blocked),
            )

        failed_attempts = _step_failed_attempts(db, task_id=task.id, step_id=ready_step.id)
        if failed_attempts > task.max_retries_per_step:
            return _fail_task(
                db,
                task,
                f"Step '{ready_step.step_key}' exhausted its retry budget after {failed_attempts} failed attempt(s).",
            )
        if failed_attempts:
            task.total_retries += 1
            task.updated_at = _utcnow()
            db.commit()

        observations = _successful_observations(db, task.id)
        try:
            await execute_agent_step(
                db,
                task_id=task.id,
                step_key=ready_step.step_key,
                user_id=user_id,
                observations=observations,
            )
        except LLMConfigurationError as exc:
            db.refresh(task)
            return _fail_task(db, task, str(exc))
        except (AgentExecutionConflictError, AgentStepNotFoundError) as exc:
            db.refresh(task)
            return _fail_task(db, task, str(exc))
        except Exception:
            # Continue only when the execution service committed a failed attempt.
            # If no attempt was persisted, fail closed rather than spin indefinitely.
            db.refresh(task)
            persisted_failures = _step_failed_attempts(
                db,
                task_id=task.id,
                step_id=ready_step.id,
            )
            if persisted_failures <= failed_attempts:
                return _fail_task(
                    db,
                    task,
                    "The step failed before an auditable tool-attempt record could be saved.",
                )
            continue
