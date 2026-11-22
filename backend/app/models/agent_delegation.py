"""Durable coordinator-to-specialist delegation records."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentDelegation(Base):
    __tablename__ = "agent_delegations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "user_id", "repository_id"],
            ["agent_tasks.id", "agent_tasks.user_id", "agent_tasks.repository_id"],
            name="fk_agent_delegations_task_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["step_id", "task_id", "user_id"],
            ["agent_steps.id", "agent_steps.task_id", "agent_steps.user_id"],
            name="fk_agent_delegations_step_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_execution_id"],
            ["agent_tool_executions.id"],
            name="fk_agent_delegations_source_execution",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "specialist_key IN ('research','code_analysis','architecture','debugging','documentation')",
            name="specialist_key_allowed",
        ),
        CheckConstraint(
            "status IN ('assigned','running','succeeded','failed','cancelled')",
            name="status_allowed",
        ),
        CheckConstraint("attempt_number BETWEEN 1 AND 3", name="attempt_number_valid"),
        CheckConstraint("length(specialist_name) BETWEEN 3 AND 100", name="specialist_name_length_valid"),
        Index("ix_agent_delegations_task_created", "task_id", "created_at"),
        Index("ix_agent_delegations_user_task", "user_id", "task_id"),
        Index("ix_agent_delegations_step_attempt", "step_id", "attempt_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    step_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    specialist_key: Mapped[str] = mapped_column(String(32), nullable=False)
    specialist_name: Mapped[str] = mapped_column(String(100), nullable=False)
    mission: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="assigned", server_default="assigned"
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    assignment_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
