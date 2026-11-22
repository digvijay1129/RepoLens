"""Persist bounded autonomous execution budgets and checkpoints.

Revision ID: 20261122_0010
Revises: 20261122_0009
Create Date: 2026-11-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261122_0010"
down_revision: Union[str, None] = "20261122_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_agent_tasks_status_allowed", "agent_tasks", type_="check")
    op.create_check_constraint(
        "ck_agent_tasks_status_allowed",
        "agent_tasks",
        "status IN ('queued','planning','planned','running','paused','awaiting_approval','completed','failed','cancelled')",
    )
    op.add_column(
        "agent_tasks",
        sa.Column("max_tool_calls", sa.Integer(), server_default="20", nullable=False),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("max_retries_per_step", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("total_tool_calls", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("total_retries", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("final_result", sa.JSON(), nullable=True),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("execution_finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_agent_tasks_max_tool_calls_valid",
        "agent_tasks",
        "max_tool_calls BETWEEN 1 AND 40",
    )
    op.create_check_constraint(
        "ck_agent_tasks_max_retries_per_step_valid",
        "agent_tasks",
        "max_retries_per_step BETWEEN 0 AND 2",
    )
    op.create_check_constraint(
        "ck_agent_tasks_total_tool_calls_nonnegative",
        "agent_tasks",
        "total_tool_calls >= 0",
    )
    op.create_check_constraint(
        "ck_agent_tasks_total_retries_nonnegative",
        "agent_tasks",
        "total_retries >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_agent_tasks_total_retries_nonnegative", "agent_tasks", type_="check")
    op.drop_constraint("ck_agent_tasks_total_tool_calls_nonnegative", "agent_tasks", type_="check")
    op.drop_constraint("ck_agent_tasks_max_retries_per_step_valid", "agent_tasks", type_="check")
    op.drop_constraint("ck_agent_tasks_max_tool_calls_valid", "agent_tasks", type_="check")
    op.drop_column("agent_tasks", "execution_finished_at")
    op.drop_column("agent_tasks", "execution_started_at")
    op.drop_column("agent_tasks", "final_result")
    op.drop_column("agent_tasks", "total_retries")
    op.drop_column("agent_tasks", "total_tool_calls")
    op.drop_column("agent_tasks", "max_retries_per_step")
    op.drop_column("agent_tasks", "max_tool_calls")
    op.drop_constraint("ck_agent_tasks_status_allowed", "agent_tasks", type_="check")
    op.create_check_constraint(
        "ck_agent_tasks_status_allowed",
        "agent_tasks",
        "status IN ('queued','planning','planned','running','awaiting_approval','completed','failed','cancelled')",
    )
