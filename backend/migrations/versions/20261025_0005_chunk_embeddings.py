"""Persist configurable embeddings for versioned source chunks.

Revision ID: 20261025_0005
Revises: 20261025_0004
Create Date: 2026-10-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261025_0005"
down_revision: Union[str, None] = "20261025_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column(
            "embedding_status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column("repositories", sa.Column("embedding_provider", sa.String(length=50), nullable=True))
    op.add_column("repositories", sa.Column("embedding_model", sa.String(length=150), nullable=True))
    op.add_column("repositories", sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
    op.add_column(
        "repositories",
        sa.Column("last_embedded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_repositories_embedding_status_allowed"),
        "repositories",
        "embedding_status IN ('pending', 'embedding', 'embedded', 'failed')",
    )
    op.create_check_constraint(
        op.f("ck_repositories_embedding_dimensions_valid"),
        "repositories",
        "embedding_dimensions IS NULL OR embedding_dimensions BETWEEN 1 AND 8192",
    )

    op.add_column(
        "indexing_jobs",
        sa.Column("job_type", sa.String(length=20), server_default="source_indexing", nullable=False),
    )
    op.add_column("indexing_jobs", sa.Column("embedding_provider", sa.String(length=50), nullable=True))
    op.add_column("indexing_jobs", sa.Column("embedding_model", sa.String(length=150), nullable=True))
    op.add_column("indexing_jobs", sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_indexing_jobs_job_type_allowed"),
        "indexing_jobs",
        "job_type IN ('source_indexing', 'embedding')",
    )

    op.create_table(
        "repository_chunk_embeddings",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("chunk_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("dimensions > 0", name=op.f("ck_repository_chunk_embeddings_dimensions_positive")),
        sa.CheckConstraint("dimensions <= 8192", name=op.f("ck_repository_chunk_embeddings_dimensions_maximum")),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["repository_chunks.id"],
            name="fk_repository_chunk_embeddings_chunk_id_repository_chunks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            name="fk_repository_chunk_embeddings_repository_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_chunk_embeddings")),
        sa.UniqueConstraint(
            "chunk_id",
            "provider",
            "model",
            "dimensions",
            name="uq_chunk_embeddings_chunk_provider_model_dimensions",
        ),
    )
    op.create_index(
        "ix_chunk_embeddings_user_repo_commit_model",
        "repository_chunk_embeddings",
        ["user_id", "repository_id", "commit_sha", "provider", "model", "dimensions"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chunk_embeddings_user_repo_commit_model", table_name="repository_chunk_embeddings")
    op.drop_table("repository_chunk_embeddings")
    op.drop_constraint(op.f("ck_indexing_jobs_job_type_allowed"), "indexing_jobs", type_="check")
    for column_name in ("embedding_dimensions", "embedding_model", "embedding_provider", "job_type"):
        op.drop_column("indexing_jobs", column_name)
    op.drop_constraint(op.f("ck_repositories_embedding_dimensions_valid"), "repositories", type_="check")
    op.drop_constraint(op.f("ck_repositories_embedding_status_allowed"), "repositories", type_="check")
    for column_name in (
        "last_embedded_at",
        "embedding_dimensions",
        "embedding_model",
        "embedding_provider",
        "embedding_status",
    ):
        op.drop_column("repositories", column_name)
