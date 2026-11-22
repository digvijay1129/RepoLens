"""Persist audit records for read-only agent tool executions.

Revision ID: 20261122_0009
Revises: 20261122_0008
Create Date: 2026-11-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261122_0009"
down_revision: Union[str, None] = "20261122_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_agent_steps_id_task_user",
        "agent_steps",
        ["id", "task_id", "user_id"],
    )
    op.create_table(
        "agent_tool_executions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("step_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("provider_call_id", sa.String(length=128), nullable=True),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="running", nullable=False),
        sa.Column("tool_input", sa.JSON(), nullable=False),
        sa.Column("tool_output", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed')",
            name=op.f("ck_agent_tool_executions_status_allowed"),
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name=op.f("ck_agent_tool_executions_duration_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "user_id", "repository_id"],
            ["agent_tasks.id", "agent_tasks.user_id", "agent_tasks.repository_id"],
            name="fk_agent_tool_executions_task_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["step_id", "task_id", "user_id"],
            ["agent_steps.id", "agent_steps.task_id", "agent_steps.user_id"],
            name="fk_agent_tool_executions_step_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_tool_executions")),
    )
    op.create_index(
        "ix_agent_tool_executions_task_created",
        "agent_tool_executions",
        ["task_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_tool_executions_user_created",
        "agent_tool_executions",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_tool_executions_user_created", table_name="agent_tool_executions")
    op.drop_index("ix_agent_tool_executions_task_created", table_name="agent_tool_executions")
    op.drop_table("agent_tool_executions")
    op.drop_constraint("uq_agent_steps_id_task_user", "agent_steps", type_="unique")
