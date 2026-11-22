"""Add task approval policy and durable human approval decisions.

Revision ID: 20261122_0013
Revises: 20261122_0012
Create Date: 2026-11-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261122_0013"
down_revision: Union[str, None] = "20261122_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_tasks",
        sa.Column("approval_mode", sa.String(length=20), server_default="auto", nullable=False),
    )
    op.create_check_constraint(
        "approval_mode_allowed",
        "agent_tasks",
        "approval_mode IN ('auto','approve_each')",
    )

    op.drop_constraint(
        op.f("ck_agent_tool_executions_status_allowed"),
        "agent_tool_executions",
        type_="check",
    )
    op.create_check_constraint(
        "status_allowed",
        "agent_tool_executions",
        "status IN ('running','awaiting_approval','succeeded','failed')",
    )

    op.create_table(
        "agent_approval_requests",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("step_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("delegation_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("proposed_execution_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("executed_execution_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("approval_mode", sa.String(length=20), server_default="approve_each", nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("tool_arguments", sa.JSON(), nullable=False),
        sa.Column("provider_call_id", sa.String(length=128), nullable=True),
        sa.Column("action_hash", sa.String(length=64), nullable=False),
        sa.Column("specialist_key", sa.String(length=32), nullable=False),
        sa.Column("policy_reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("decision_comment", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','approved','denied','expired','cancelled','executed')",
            name=op.f("ck_agent_approval_requests_status_allowed"),
        ),
        sa.CheckConstraint(
            "approval_mode IN ('approve_each')",
            name=op.f("ck_agent_approval_requests_approval_mode_allowed"),
        ),
        sa.CheckConstraint(
            "specialist_key IN ('research','code_analysis','architecture','debugging','documentation')",
            name=op.f("ck_agent_approval_requests_specialist_key_allowed"),
        ),
        sa.CheckConstraint(
            "length(tool_name) BETWEEN 1 AND 80",
            name=op.f("ck_agent_approval_requests_tool_name_length_valid"),
        ),
        sa.CheckConstraint(
            "length(action_hash) = 64",
            name=op.f("ck_agent_approval_requests_action_hash_length_valid"),
        ),
        sa.CheckConstraint(
            "length(policy_reason) BETWEEN 8 AND 500",
            name=op.f("ck_agent_approval_requests_policy_reason_length_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "user_id", "repository_id"],
            ["agent_tasks.id", "agent_tasks.user_id", "agent_tasks.repository_id"],
            name="fk_agent_approval_requests_task_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["step_id", "task_id", "user_id"],
            ["agent_steps.id", "agent_steps.task_id", "agent_steps.user_id"],
            name="fk_agent_approval_requests_step_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["delegation_id"],
            ["agent_delegations.id"],
            name="fk_agent_approval_requests_delegation",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["proposed_execution_id"],
            ["agent_tool_executions.id"],
            name="fk_agent_approval_requests_proposed_execution",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["executed_execution_id"],
            ["agent_tool_executions.id"],
            name="fk_agent_approval_requests_executed_execution",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["users.id"],
            name=op.f("fk_agent_approval_requests_decided_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_approval_requests")),
    )
    op.create_index(
        "ix_agent_approval_requests_task_status",
        "agent_approval_requests",
        ["task_id", "status", "requested_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_approval_requests_user_status",
        "agent_approval_requests",
        ["user_id", "status", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_approval_requests_step_created",
        "agent_approval_requests",
        ["step_id", "requested_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_approval_requests_step_created", table_name="agent_approval_requests")
    op.drop_index("ix_agent_approval_requests_user_status", table_name="agent_approval_requests")
    op.drop_index("ix_agent_approval_requests_task_status", table_name="agent_approval_requests")
    op.drop_table("agent_approval_requests")
    op.drop_constraint(op.f("ck_agent_tool_executions_status_allowed"), "agent_tool_executions", type_="check")
    op.create_check_constraint(
        "status_allowed",
        "agent_tool_executions",
        "status IN ('running','succeeded','failed')",
    )
    op.drop_constraint(op.f("ck_agent_tasks_approval_mode_allowed"), "agent_tasks", type_="check")
    op.drop_column("agent_tasks", "approval_mode")
