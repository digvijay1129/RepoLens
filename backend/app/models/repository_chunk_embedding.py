"""Versioned source-chunk embeddings stored in pgvector on PostgreSQL.

SQLite uses JSON only for isolated unit tests; production PostgreSQL uses the
native pgvector type so cosine-distance queries execute inside the database.
"""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VectorOrJSON(TypeDecorator):
    """Use native PostgreSQL vector storage and JSON only for SQLite unit tests."""

    impl = JSON
    cache_ok = True
    comparator_factory = Vector.comparator_factory

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        return [float(item) for item in value]

    def process_result_value(self, value: Any, dialect):
        if value is None:
            return None
        return [float(item) for item in value]


class RepositoryChunkEmbedding(Base):
    __tablename__ = "repository_chunk_embeddings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chunk_id"],
            ["repository_chunks.id"],
            name="fk_repository_chunk_embeddings_chunk_id_repository_chunks",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            name="fk_repository_chunk_embeddings_repository_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "chunk_id",
            "provider",
            "model",
            "dimensions",
            name="uq_chunk_embeddings_chunk_provider_model_dimensions",
        ),
        CheckConstraint("dimensions > 0", name="dimensions_positive"),
        CheckConstraint("dimensions <= 8192", name="dimensions_maximum"),
        Index(
            "ix_chunk_embeddings_user_repo_commit_model",
            "user_id",
            "repository_id",
            "commit_sha",
            "provider",
            "model",
            "dimensions",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(150), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    vector: Mapped[list[float]] = mapped_column(VectorOrJSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    chunk: Mapped["RepositoryChunk"] = relationship(back_populates="embeddings")
