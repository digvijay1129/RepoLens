"""Authenticated endpoints for Phase 1 agent task planning and inspection."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.execution import (
    AgentExecutionConflictError,
    AgentStepNotFoundError,
    execute_agent_step,
    list_agent_tools,
    list_tool_executions,
)
from app.agents.memory import (
    AgentMemoryLimitError,
    AgentMemoryNotFoundError,
    create_repository_memory,
    delete_repository_memory,
    list_repository_memories,
    update_repository_memory,
)
from app.agents.planner import AgentPlanningError
from app.agents.runner import (
    AgentRunConflictError,
    AgentRunNotFoundError,
    run_agent_task,
)
from app.agents.schemas import (
    AgentGoalRequest,
    AgentMemoryCreateRequest,
    AgentMemoryResponse,
    AgentMemoryUpdateRequest,
    AgentRunRequest,
    AgentStepExecutionRequest,
    AgentTaskStatus,
)
from app.agents.tools import AgentToolError
from app.agents.service import (
    AgentRepositoryNotReadyError,
    AgentTaskNotFoundError,
    cancel_agent_task,
    create_agent_task,
    get_agent_task,
    list_agent_tasks,
    serialize_task,
)
from app.api.dependencies import get_current_user
from app.api.schemas.agents import (
    AgentTaskDetail,
    AgentTaskSummary,
    AgentToolExecutionResponse,
)
from app.db.session import get_db_session
from app.models.repository import Repository
from app.models.user import User
from app.services.llm import LLMConfigurationError, LLMProviderError

router = APIRouter()


def _owned_repository(db: Session, repository_id: uuid.UUID, user_id: uuid.UUID) -> Repository:
    repository = db.scalar(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == user_id,
        )
    )
    if repository is None:
        raise HTTPException(status_code=404, detail="Saved repository was not found.")
    return repository


@router.post(
    "/tasks",
    response_model=AgentTaskDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create an agent task and generate its declarative plan",
)
async def create_task(
    body: AgentGoalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    repository = _owned_repository(db, body.repository_id, current_user.id)
    try:
        task = await create_agent_task(
            db,
            user_id=current_user.id,
            repository=repository,
            goal=body.goal,
            max_steps=body.max_steps,
        )
        return serialize_task(task)
    except AgentRepositoryNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AgentPlanningError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/tasks",
    response_model=list[AgentTaskSummary],
    summary="List the current user's agent tasks",
)
def get_tasks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    repository_id: uuid.UUID | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[dict]:
    return [
        {
            "id": task.id,
            "repository_id": task.repository_id,
            "goal": task.goal,
            "status": task.status,
            "max_steps": task.max_steps,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        }
        for task in list_agent_tasks(
            db,
            user_id=current_user.id,
            repository_id=repository_id,
            limit=limit,
        )
    ]


@router.get(
    "/tasks/{task_id}",
    response_model=AgentTaskDetail,
    summary="Get an owner-scoped agent task and its plan",
)
def get_task(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        return serialize_task(get_agent_task(db, task_id=task_id, user_id=current_user.id))
    except AgentTaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/tasks/{task_id}/cancel",
    response_model=AgentTaskDetail,
    summary="Cancel a queued, planned, paused, or running agent task",
)
def cancel_task(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        task = cancel_agent_task(db, task_id=task_id, user_id=current_user.id)
        return serialize_task(task)
    except AgentTaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc



@router.get(
    "/tasks/{task_id}/tools",
    summary="List the read-only tools available to a planned agent task",
)
def get_task_tools(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict]:
    try:
        return list_agent_tools(db, task_id=task_id, user_id=current_user.id)
    except AgentStepNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/tasks/{task_id}/tool-executions",
    response_model=list[AgentToolExecutionResponse],
    summary="List the audit history of read-only tool executions",
)
def get_task_tool_executions(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict]:
    try:
        return list_tool_executions(db, task_id=task_id, user_id=current_user.id)
    except AgentStepNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/tasks/{task_id}/steps/{step_key}/execute",
    response_model=AgentToolExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Select and execute one read-only tool for a planned step",
)
async def execute_task_step(
    task_id: uuid.UUID,
    step_key: str,
    body: AgentStepExecutionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        return await execute_agent_step(
            db,
            task_id=task_id,
            step_key=step_key,
            user_id=current_user.id,
            instruction=body.instruction,
        )
    except AgentStepNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (LLMProviderError, AgentToolError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc



@router.post(
    "/tasks/{task_id}/run",
    response_model=AgentTaskDetail,
    summary="Run a bounded autonomous Plan-Act-Observe-Decide task",
)
async def run_task(
    task_id: uuid.UUID,
    body: AgentRunRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        return await run_agent_task(
            db,
            task_id=task_id,
            user_id=current_user.id,
            max_tool_calls=body.max_tool_calls,
            max_retries_per_step=body.max_retries_per_step,
            max_runtime_seconds=body.max_runtime_seconds,
        )
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/tasks/{task_id}/resume",
    response_model=AgentTaskDetail,
    summary="Resume a paused or interrupted autonomous task",
)
async def resume_task(
    task_id: uuid.UUID,
    body: AgentRunRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        return await run_agent_task(
            db,
            task_id=task_id,
            user_id=current_user.id,
            max_tool_calls=body.max_tool_calls,
            max_retries_per_step=body.max_retries_per_step,
            max_runtime_seconds=body.max_runtime_seconds,
        )
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentRunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc



@router.get(
    "/repositories/{repository_id}/memories",
    response_model=list[AgentMemoryResponse],
    summary="List and search memories for an owned repository",
)
def get_repository_memories(
    repository_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    query: str | None = Query(default=None, max_length=1200),
    memory_type: str | None = Query(default=None),
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict]:
    try:
        return list_repository_memories(
            db,
            repository_id=repository_id,
            user_id=current_user.id,
            query=query,
            memory_type=memory_type,
            include_inactive=include_inactive,
            limit=limit,
        )
    except AgentMemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/repositories/{repository_id}/memories",
    response_model=AgentMemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user-curated repository memory",
)
def create_memory(
    repository_id: uuid.UUID,
    body: AgentMemoryCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        return create_repository_memory(
            db,
            repository_id=repository_id,
            user_id=current_user.id,
            memory_type=body.memory_type,
            title=body.title,
            content=body.content,
            tags=body.tags,
            importance=body.importance,
            confidence=body.confidence,
            expires_at=body.expires_at,
        )
    except AgentMemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentMemoryLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch(
    "/memories/{memory_id}",
    response_model=AgentMemoryResponse,
    summary="Update an owned repository memory",
)
def patch_memory(
    memory_id: uuid.UUID,
    body: AgentMemoryUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        return update_repository_memory(
            db,
            memory_id=memory_id,
            user_id=current_user.id,
            updates=body.model_dump(exclude_unset=True),
        )
    except AgentMemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentMemoryLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/memories/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete an owned repository memory",
)
def remove_memory(
    memory_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> Response:
    try:
        delete_repository_memory(db, memory_id=memory_id, user_id=current_user.id)
    except AgentMemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
