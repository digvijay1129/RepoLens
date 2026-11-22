"""Create durable coordinator specialist delegation records.

Revision ID: 20261122_0012
Revises: 20261122_0011
Create Date: 2026-11-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261122_0012"
down_revision: Union[str, None] = "20261122_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_delegations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("step_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_execution_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("specialist_key", sa.String(length=32), nullable=False),
        sa.Column("specialist_name", sa.String(length=100), nullable=False),
        sa.Column("mission", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="assigned", nullable=False),
        sa.Column("attempt_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("assignment_context", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "specialist_key IN ('research','code_analysis','architecture','debugging','documentation')",
            name=op.f("ck_agent_delegations_specialist_key_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('assigned','running','succeeded','failed','cancelled')",
            name=op.f("ck_agent_delegations_status_allowed"),
        ),
        sa.CheckConstraint(
            "attempt_number BETWEEN 1 AND 3",
            name=op.f("ck_agent_delegations_attempt_number_valid"),
        ),
        sa.CheckConstraint(
            "length(specialist_name) BETWEEN 3 AND 100",
            name=op.f("ck_agent_delegations_specialist_name_length_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "user_id", "repository_id"],
            ["agent_tasks.id", "agent_tasks.user_id", "agent_tasks.repository_id"],
            name="fk_agent_delegations_task_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["step_id", "task_id", "user_id"],
            ["agent_steps.id", "agent_steps.task_id", "agent_steps.user_id"],
            name="fk_agent_delegations_step_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_execution_id"],
            ["agent_tool_executions.id"],
            name="fk_agent_delegations_source_execution",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_delegations")),
    )
    op.create_index(
        "ix_agent_delegations_task_created",
        "agent_delegations",
        ["task_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_delegations_user_task",
        "agent_delegations",
        ["user_id", "task_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_delegations_step_attempt",
        "agent_delegations",
        ["step_id", "attempt_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_delegations_step_attempt", table_name="agent_delegations")
    op.drop_index("ix_agent_delegations_user_task", table_name="agent_delegations")
    op.drop_index("ix_agent_delegations_task_created", table_name="agent_delegations")
    op.drop_table("agent_delegations")
