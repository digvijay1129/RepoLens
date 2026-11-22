"""Versioned declarative plans created for agent tasks."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentPlan(Base):
    __tablename__ = "agent_plans"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "user_id", "repository_id"],
            ["agent_tasks.id", "agent_tasks.user_id", "agent_tasks.repository_id"],
            name="fk_agent_plans_task_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "task_id", "user_id", name="uq_agent_plans_id_task_user"),
        UniqueConstraint("task_id", "version", name="uq_agent_plans_task_version"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    completion_criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    assumptions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    planner_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    planner_model: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    task = relationship(
        "AgentTask",
        back_populates="plan",
        foreign_keys=[task_id, user_id, repository_id],
    )
    steps = relationship(
        "AgentStep",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="AgentStep.position",
        foreign_keys="[AgentStep.plan_id, AgentStep.task_id, AgentStep.user_id]",
    )
