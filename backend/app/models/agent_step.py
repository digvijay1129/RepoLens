"""Ordered plan steps for a task, ready for later execution phases."""

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


class AgentStep(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "user_id", "repository_id"],
            ["agent_tasks.id", "agent_tasks.user_id", "agent_tasks.repository_id"],
            name="fk_agent_steps_task_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["plan_id", "task_id", "user_id"],
            ["agent_plans.id", "agent_plans.task_id", "agent_plans.user_id"],
            name="fk_agent_steps_plan_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("task_id", "position", name="uq_agent_steps_task_position"),
        UniqueConstraint("task_id", "step_key", name="uq_agent_steps_task_step_key"),
        CheckConstraint("position >= 1", name="position_positive"),
        CheckConstraint(
            "status IN ('pending','ready','running','succeeded','failed','skipped','blocked')",
            name="status_allowed",
        ),
        CheckConstraint("length(title) BETWEEN 3 AND 160", name="title_length_valid"),
        CheckConstraint("length(step_key) BETWEEN 2 AND 50", name="step_key_length_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(String(500), nullable=False)
    suggested_tool: Mapped[str | None] = mapped_column(String(80), nullable=True)
    depends_on: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    task = relationship(
        "AgentTask",
        back_populates="steps",
        foreign_keys=[task_id, user_id, repository_id],
    )
    plan = relationship(
        "AgentPlan",
        back_populates="steps",
        foreign_keys=[plan_id, task_id, user_id],
    )
