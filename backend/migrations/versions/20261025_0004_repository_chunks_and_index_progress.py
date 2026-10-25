"""Add durable indexing-job progress and repository source chunks.

Revision ID: 20261025_0004
Revises: 20261025_0003
Create Date: 2026-10-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261025_0004"
down_revision: Union[str, None] = "20261025_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "indexing_jobs",
        sa.Column("total_files", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "indexing_jobs",
        sa.Column("processed_files", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "indexing_jobs",
        sa.Column("skipped_files", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "indexing_jobs",
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("indexing_jobs", sa.Column("commit_sha", sa.String(length=40), nullable=True))
    op.add_column(
        "indexing_jobs",
        sa.Column(
            "progress_message",
            sa.String(length=250),
            server_default="Queued for indexing",
            nullable=False,
        ),
    )

    for constraint_name, expression in (
        ("total_files_nonnegative", "total_files >= 0"),
        ("processed_files_nonnegative", "processed_files >= 0"),
        ("skipped_files_nonnegative", "skipped_files >= 0"),
        ("chunk_count_nonnegative", "chunk_count >= 0"),
    ):
        op.create_check_constraint(
            op.f(f"ck_indexing_jobs_{constraint_name}"),
            "indexing_jobs",
            expression,
        )

    op.create_table(
        "repository_chunks",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("language", sa.String(length=30), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("symbol_names", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name=op.f("ck_repository_chunks_chunk_index_nonnegative"),
        ),
        sa.CheckConstraint(
            "start_line >= 1",
            name=op.f("ck_repository_chunks_start_line_positive"),
        ),
        sa.CheckConstraint(
            "end_line >= start_line",
            name=op.f("ck_repository_chunks_end_line_valid"),
        ),
        sa.CheckConstraint(
            "token_count >= 0",
            name=op.f("ck_repository_chunks_token_count_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            name="fk_repository_chunks_repository_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_chunks")),
        sa.UniqueConstraint(
            "repository_id",
            "user_id",
            "commit_sha",
            "file_path",
            "chunk_index",
            name="uq_repository_chunks_repo_snapshot_file_chunk",
        ),
    )
    op.create_index(
        "ix_repository_chunks_user_repo_commit",
        "repository_chunks",
        ["user_id", "repository_id", "commit_sha"],
        unique=False,
    )
    op.create_index(
        "ix_repository_chunks_user_repo_path",
        "repository_chunks",
        ["user_id", "repository_id", "file_path"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_repository_chunks_user_repo_path", table_name="repository_chunks")
    op.drop_index("ix_repository_chunks_user_repo_commit", table_name="repository_chunks")
    op.drop_table("repository_chunks")
    for constraint_name in (
        "chunk_count_nonnegative",
        "skipped_files_nonnegative",
        "processed_files_nonnegative",
        "total_files_nonnegative",
    ):
        op.drop_constraint(
            op.f(f"ck_indexing_jobs_{constraint_name}"),
            "indexing_jobs",
            type_="check",
        )
    for column_name in (
        "progress_message",
        "commit_sha",
        "chunk_count",
        "skipped_files",
        "processed_files",
        "total_files",
    ):
        op.drop_column("indexing_jobs", column_name)
