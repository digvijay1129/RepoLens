"""Single planned-step execution through the controlled read-only tool registry."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.schemas import AgentTaskStatus
from app.agents.tool_calling import select_tool_call
from app.agents.tools import (
    AgentToolContext,
    AgentToolError,
    build_agent_tool_registry,
)
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


async def execute_agent_step(
    db: Session,
    *,
    task_id: uuid.UUID,
    step_key: str,
    user_id: uuid.UUID,
    instruction: str | None = None,
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Select and execute exactly one allowlisted read-only tool for one plan step."""
    task = db.scalar(
        select(AgentTask)
        .where(AgentTask.id == task_id, AgentTask.user_id == user_id)
        .with_for_update()
    )
    if task is None:
        raise AgentStepNotFoundError("Agent task was not found.")
    if task.status not in {AgentTaskStatus.PLANNED.value, AgentTaskStatus.RUNNING.value}:
        raise AgentExecutionConflictError("Only planned or running tasks can execute an individual step.")
    if task.total_tool_calls >= task.max_tool_calls:
        raise AgentExecutionConflictError("The task has reached its maximum tool-call budget.")

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
        },
    )
    step.status = "running"
    task.total_tool_calls += 1
    task.updated_at = datetime.now(timezone.utc)
    db.add(execution)
    db.commit()
    db.refresh(execution)

    try:
        registry = build_agent_tool_registry()
        selected = await select_tool_call(
            task,
            step,
            registry,
            instruction=instruction,
            observations=observations,
        )
        definition = registry.get(selected.name)
        execution.provider_call_id = selected.call_id
        execution.tool_name = definition.name
        execution.tool_input = {
            "step_key": step.step_key,
            "arguments": selected.arguments,
            "instruction": instruction or "",
        }
        db.flush()

        output = await registry.execute(
            selected.name,
            selected.arguments,
            AgentToolContext(db=db, repository=repository, user_id=user_id),
        )
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        execution.status = "succeeded"
        execution.tool_output = output
        execution.error_message = None
        execution.duration_ms = duration_ms
        execution.finished_at = datetime.now(timezone.utc)
        step.status = "succeeded"
        step.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(execution)
        return _serialize_execution(execution)
    except (AgentToolError, LLMConfigurationError, LLMProviderError) as exc:
        db.rollback()
        execution = db.get(AgentToolExecution, execution.id)
        step = db.get(AgentStep, step.id)
        if execution is not None:
            execution.status = "failed"
            execution.error_message = str(exc)[:1000]
            execution.duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            execution.finished_at = datetime.now(timezone.utc)
        if step is not None:
            step.status = "failed"
            step.updated_at = datetime.now(timezone.utc)
        db.commit()
        raise
    except Exception as exc:
        db.rollback()
        execution = db.get(AgentToolExecution, execution.id)
        step = db.get(AgentStep, step.id)
        if execution is not None:
            execution.status = "failed"
            execution.error_message = "Tool execution failed unexpectedly."
            execution.duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            execution.finished_at = datetime.now(timezone.utc)
        if step is not None:
            step.status = "failed"
            step.updated_at = datetime.now(timezone.utc)
        db.commit()
        raise AgentToolError("Tool execution failed unexpectedly.") from exc
