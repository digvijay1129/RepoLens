"""Authenticated endpoints for Phase 1 agent task planning and inspection."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.planner import AgentPlanningError
from app.agents.schemas import AgentGoalRequest, AgentTaskStatus
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
from app.api.schemas.agents import AgentTaskDetail, AgentTaskSummary
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
    summary="Cancel a queued or planned agent task",
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
