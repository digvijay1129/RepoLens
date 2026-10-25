"""Persisted text chunks created by a completed repository indexing snapshot."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RepositoryChunk(Base):
    __tablename__ = "repository_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            name="fk_repository_chunks_repository_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "repository_id",
            "user_id",
            "commit_sha",
            "file_path",
            "chunk_index",
            name="uq_repository_chunks_repo_snapshot_file_chunk",
        ),
        CheckConstraint("chunk_index >= 0", name="chunk_index_nonnegative"),
        CheckConstraint("start_line >= 1", name="start_line_positive"),
        CheckConstraint("end_line >= start_line", name="end_line_valid"),
        CheckConstraint("token_count >= 0", name="token_count_nonnegative"),
        Index(
            "ix_repository_chunks_user_repo_commit",
            "user_id",
            "repository_id",
            "commit_sha",
        ),
        Index(
            "ix_repository_chunks_user_repo_path",
            "user_id",
            "repository_id",
            "file_path",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    language: Mapped[str] = mapped_column(String(30), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol_names: Mapped[str] = mapped_column(String(1000), nullable=False, default="", server_default="")
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    repository: Mapped["Repository"] = relationship(
        back_populates="chunks",
        foreign_keys="[RepositoryChunk.repository_id, RepositoryChunk.user_id]",
    )
