"""Owner-scoped agent task records."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
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


class AgentTask(Base):
    __tablename__ = "agent_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            name="fk_agent_tasks_repository_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "id", "user_id", "repository_id",
            name="uq_agent_tasks_id_user_repository",
        ),
        CheckConstraint(
            "status IN ('queued','planning','planned','running','paused','awaiting_approval','completed','failed','cancelled')",
            name="status_allowed",
        ),
        CheckConstraint("max_steps BETWEEN 1 AND 20", name="max_steps_valid"),
        CheckConstraint("max_tool_calls BETWEEN 1 AND 40", name="max_tool_calls_valid"),
        CheckConstraint("max_retries_per_step BETWEEN 0 AND 2", name="max_retries_per_step_valid"),
        CheckConstraint("total_tool_calls >= 0", name="total_tool_calls_nonnegative"),
        CheckConstraint("total_retries >= 0", name="total_retries_nonnegative"),
        CheckConstraint("length(goal) BETWEEN 8 AND 4000", name="goal_length_valid"),
        Index("ix_agent_tasks_user_created", "user_id", "created_at"),
        Index("ix_agent_tasks_repository_created", "repository_id", "created_at"),
        Index("ix_agent_tasks_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    indexed_commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="queued", server_default="queued"
    )
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=8, server_default="8")
    max_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=20, server_default="20")
    max_retries_per_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    total_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    final_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    execution_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    repository = relationship("Repository", foreign_keys=[repository_id, user_id])
    plan = relationship(
        "AgentPlan",
        back_populates="task",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="[AgentPlan.task_id, AgentPlan.user_id, AgentPlan.repository_id]",
    )
    steps = relationship(
        "AgentStep",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="AgentStep.position",
        foreign_keys="[AgentStep.task_id, AgentStep.user_id, AgentStep.repository_id]",
        overlaps="plan,steps",
    )
