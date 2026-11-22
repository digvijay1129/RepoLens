"""Owner-scoped human approval requests for proposed agent actions."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentApprovalRequest(Base):
    __tablename__ = "agent_approval_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "user_id", "repository_id"],
            ["agent_tasks.id", "agent_tasks.user_id", "agent_tasks.repository_id"],
            name="fk_agent_approval_requests_task_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["step_id", "task_id", "user_id"],
            ["agent_steps.id", "agent_steps.task_id", "agent_steps.user_id"],
            name="fk_agent_approval_requests_step_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["delegation_id"],
            ["agent_delegations.id"],
            name="fk_agent_approval_requests_delegation",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["proposed_execution_id"],
            ["agent_tool_executions.id"],
            name="fk_agent_approval_requests_proposed_execution",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["executed_execution_id"],
            ["agent_tool_executions.id"],
            name="fk_agent_approval_requests_executed_execution",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('pending','approved','denied','expired','cancelled','executed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "approval_mode IN ('approve_each')",
            name="approval_mode_allowed",
        ),
        CheckConstraint(
            "specialist_key IN ('research','code_analysis','architecture','debugging','documentation')",
            name="specialist_key_allowed",
        ),
        CheckConstraint("length(tool_name) BETWEEN 1 AND 80", name="tool_name_length_valid"),
        CheckConstraint("length(action_hash) = 64", name="action_hash_length_valid"),
        CheckConstraint("length(policy_reason) BETWEEN 8 AND 500", name="policy_reason_length_valid"),
        Index("ix_agent_approval_requests_task_status", "task_id", "status", "requested_at"),
        Index("ix_agent_approval_requests_user_status", "user_id", "status", "expires_at"),
        Index("ix_agent_approval_requests_step_created", "step_id", "requested_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    step_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    delegation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    proposed_execution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    executed_execution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    approval_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="approve_each", server_default="approve_each"
    )
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    tool_arguments: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provider_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    specialist_key: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision_comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
