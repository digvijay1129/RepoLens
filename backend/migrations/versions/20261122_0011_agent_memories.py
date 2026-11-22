"""Create owner-scoped persistent repository agent memories.

Revision ID: 20261122_0011
Revises: 20261122_0010
Create Date: 2026-11-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261122_0011"
down_revision: Union[str, None] = "20261122_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("source_execution_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("memory_type", sa.String(length=24), nullable=False),
        sa.Column("origin", sa.String(length=12), server_default="user", nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("source_commit_sha", sa.String(length=40), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("importance", sa.Integer(), server_default="3", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("access_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "memory_type IN ('architecture','convention','decision','troubleshooting','note','observation')",
            name=op.f("ck_agent_memories_memory_type_allowed"),
        ),
        sa.CheckConstraint("origin IN ('user','agent')", name=op.f("ck_agent_memories_origin_allowed")),
        sa.CheckConstraint("importance BETWEEN 1 AND 5", name=op.f("ck_agent_memories_importance_valid")),
        sa.CheckConstraint("confidence BETWEEN 0.0 AND 1.0", name=op.f("ck_agent_memories_confidence_valid")),
        sa.CheckConstraint("length(title) BETWEEN 3 AND 160", name=op.f("ck_agent_memories_title_length_valid")),
        sa.CheckConstraint("length(content) BETWEEN 8 AND 6000", name=op.f("ck_agent_memories_content_length_valid")),
        sa.CheckConstraint("access_count >= 0", name=op.f("ck_agent_memories_access_count_nonnegative")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_agent_memories_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id", "user_id"], ["repositories.id", "repositories.user_id"],
            name="fk_agent_memories_repository_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "user_id", "repository_id"],
            ["agent_tasks.id", "agent_tasks.user_id", "agent_tasks.repository_id"],
            name="fk_agent_memories_task_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_execution_id"], ["agent_tool_executions.id"],
            name="fk_agent_memories_source_execution",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_memories")),
        sa.UniqueConstraint(
            "user_id", "repository_id", "content_hash",
            name="uq_agent_memories_user_repo_hash",
        ),
    )
    op.create_index(
        "ix_agent_memories_user_repo_active",
        "agent_memories",
        ["user_id", "repository_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_agent_memories_repo_commit",
        "agent_memories",
        ["repository_id", "source_commit_sha"],
        unique=False,
    )
    op.create_index(
        "ix_agent_memories_repo_updated",
        "agent_memories",
        ["repository_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_memories_repo_updated", table_name="agent_memories")
    op.drop_index("ix_agent_memories_repo_commit", table_name="agent_memories")
    op.drop_index("ix_agent_memories_user_repo_active", table_name="agent_memories")
    op.drop_table("agent_memories")
