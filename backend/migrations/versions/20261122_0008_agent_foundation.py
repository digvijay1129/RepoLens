"""Create persistent owner-scoped agent tasks, plans, and steps.

Revision ID: 20261122_0008
Revises: 20261025_0007
Create Date: 2026-11-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261122_0008"
down_revision: Union[str, None] = "20261025_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("indexed_commit_sha", sa.String(length=40), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="queued", nullable=False),
        sa.Column("max_steps", sa.Integer(), server_default="8", nullable=False),
        sa.Column("latest_error", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','planning','planned','running','awaiting_approval','completed','failed','cancelled')",
            name=op.f("ck_agent_tasks_status_allowed"),
        ),
        sa.CheckConstraint("max_steps BETWEEN 1 AND 20", name=op.f("ck_agent_tasks_max_steps_valid")),
        sa.CheckConstraint("length(goal) BETWEEN 8 AND 4000", name=op.f("ck_agent_tasks_goal_length_valid")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_agent_tasks_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            name="fk_agent_tasks_repository_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_tasks")),
        sa.UniqueConstraint("id", "user_id", "repository_id", name="uq_agent_tasks_id_user_repository"),
    )
    op.create_index("ix_agent_tasks_user_created", "agent_tasks", ["user_id", "created_at"], unique=False)
    op.create_index("ix_agent_tasks_repository_created", "agent_tasks", ["repository_id", "created_at"], unique=False)
    op.create_index("ix_agent_tasks_user_status", "agent_tasks", ["user_id", "status"], unique=False)

    op.create_table(
        "agent_plans",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("completion_criteria", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("planner_provider", sa.String(length=50), nullable=False),
        sa.Column("planner_model", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_agent_plans_version_positive")),
        sa.ForeignKeyConstraint(
            ["task_id", "user_id", "repository_id"],
            ["agent_tasks.id", "agent_tasks.user_id", "agent_tasks.repository_id"],
            name="fk_agent_plans_task_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_plans")),
        sa.UniqueConstraint("id", "task_id", "user_id", name="uq_agent_plans_id_task_user"),
        sa.UniqueConstraint("task_id", "version", name="uq_agent_plans_task_version"),
    )

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("plan_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.String(length=500), nullable=False),
        sa.Column("suggested_tool", sa.String(length=80), nullable=True),
        sa.Column("depends_on", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("position >= 1", name=op.f("ck_agent_steps_position_positive")),
        sa.CheckConstraint(
            "status IN ('pending','ready','running','succeeded','failed','skipped','blocked')",
            name=op.f("ck_agent_steps_status_allowed"),
        ),
        sa.CheckConstraint("length(title) BETWEEN 3 AND 160", name=op.f("ck_agent_steps_title_length_valid")),
        sa.ForeignKeyConstraint(
            ["task_id", "user_id", "repository_id"],
            ["agent_tasks.id", "agent_tasks.user_id", "agent_tasks.repository_id"],
            name="fk_agent_steps_task_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id", "task_id", "user_id"],
            ["agent_plans.id", "agent_plans.task_id", "agent_plans.user_id"],
            name="fk_agent_steps_plan_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_steps")),
        sa.UniqueConstraint("task_id", "position", name="uq_agent_steps_task_position"),
        sa.UniqueConstraint("task_id", "step_key", name="uq_agent_steps_task_step_key"),
    )


def downgrade() -> None:
    op.drop_table("agent_steps")
    op.drop_table("agent_plans")
    op.drop_index("ix_agent_tasks_user_status", table_name="agent_tasks")
    op.drop_index("ix_agent_tasks_repository_created", table_name="agent_tasks")
    op.drop_index("ix_agent_tasks_user_created", table_name="agent_tasks")
    op.drop_table("agent_tasks")
