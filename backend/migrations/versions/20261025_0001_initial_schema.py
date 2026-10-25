"""Create workspace, repository, and indexing job tables.

Revision ID: 20261025_0001
Revises:
Create Date: 2026-10-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261025_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("github_owner", sa.String(length=39), nullable=False),
        sa.Column("github_name", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=140), nullable=False),
        sa.Column("canonical_url", sa.String(length=300), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column("indexed_commit_sha", sa.String(length=40), nullable=True),
        sa.Column("indexing_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "indexing_status IN ('pending', 'indexing', 'indexed', 'failed')",
            name="ck_repositories_indexing_status_allowed",
        ),
        sa.CheckConstraint("full_name = lower(full_name)", name="ck_repositories_full_name_lowercase"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_repositories_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_repositories"),
        sa.UniqueConstraint("id", "user_id", name="uq_repositories_id_user_id"),
        sa.UniqueConstraint("user_id", "full_name", name="uq_repositories_user_full_name"),
    )
    op.create_index(
        "ix_repositories_user_updated", "repositories", ["user_id", "updated_at"], unique=False
    )

    op.create_table(
        "indexing_jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_indexing_jobs_status_allowed",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_indexing_jobs_attempt_count_nonnegative"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_indexing_jobs_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            name="fk_indexing_jobs_repository_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_indexing_jobs"),
    )
    op.create_index(
        "ix_indexing_jobs_user_status_created",
        "indexing_jobs",
        ["user_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_indexing_jobs_repository_created",
        "indexing_jobs",
        ["repository_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_indexing_jobs_repository_created", table_name="indexing_jobs")
    op.drop_index("ix_indexing_jobs_user_status_created", table_name="indexing_jobs")
    op.drop_table("indexing_jobs")
    op.drop_index("ix_repositories_user_updated", table_name="repositories")
    op.drop_table("repositories")
    op.drop_table("users")
