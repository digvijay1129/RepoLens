"""Convert stored JSON embeddings to pgvector and index code chunks for keyword search.

Revision ID: 20261025_0006
Revises: 20261025_0005
Create Date: 2026-10-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "20261025_0006"
down_revision: Union[str, None] = "20261025_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The extension package must be installed on the PostgreSQL server first.
    # On deployments where the app role cannot create extensions, the DBA can
    # create it once in the database before running this migration.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "repository_chunk_embeddings",
        sa.Column("vector_pg", Vector(), nullable=True),
    )
    op.execute(
        "UPDATE repository_chunk_embeddings "
        "SET vector_pg = vector::text::vector "
        "WHERE vector IS NOT NULL"
    )
    op.drop_column("repository_chunk_embeddings", "vector")
    op.alter_column(
        "repository_chunk_embeddings",
        "vector_pg",
        new_column_name="vector",
        existing_type=Vector(),
        nullable=False,
    )

    # GIN speeds lexical matching of identifiers, docs and source text. Semantic
    # search uses cosine distance after owner/repository/model filters; that exact
    # search avoids mixing different embedding spaces in a single ANN index.
    op.execute(
        "CREATE INDEX ix_repository_chunks_fts_simple "
        "ON repository_chunks USING gin (to_tsvector('simple', chunk_text))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_repository_chunks_fts_simple")
    op.add_column(
        "repository_chunk_embeddings",
        sa.Column("vector_json", sa.JSON(), nullable=True),
    )
    op.execute(
        "UPDATE repository_chunk_embeddings "
        "SET vector_json = vector::text::json "
        "WHERE vector IS NOT NULL"
    )
    op.drop_column("repository_chunk_embeddings", "vector")
    op.alter_column(
        "repository_chunk_embeddings",
        "vector_json",
        new_column_name="vector",
        existing_type=sa.JSON(),
        nullable=False,
    )
    # Deliberately do not DROP EXTENSION: other database tables may use pgvector.
