"""Persistent background-indexing job records."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IndexingJob(Base):
    __tablename__ = "indexing_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            name="fk_indexing_jobs_repository_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "job_type IN ('source_indexing', 'embedding')",
            name="job_type_allowed",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        CheckConstraint("total_files >= 0", name="total_files_nonnegative"),
        CheckConstraint("processed_files >= 0", name="processed_files_nonnegative"),
        CheckConstraint("skipped_files >= 0", name="skipped_files_nonnegative"),
        CheckConstraint("chunk_count >= 0", name="chunk_count_nonnegative"),
        Index("ix_indexing_jobs_user_status_created", "user_id", "status", "created_at"),
        Index("ix_indexing_jobs_repository_created", "repository_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", server_default="queued"
    )
    job_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="source_indexing", server_default="source_indexing"
    )
    embedding_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    processed_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    progress_message: Mapped[str] = mapped_column(
        String(250), nullable=False, default="Queued for indexing", server_default="Queued for indexing"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(
        back_populates="indexing_jobs",
        foreign_keys=[user_id],
        overlaps="repository,indexing_jobs",
    )
    repository: Mapped["Repository"] = relationship(
        back_populates="indexing_jobs",
        foreign_keys="[IndexingJob.repository_id, IndexingJob.user_id]",
        overlaps="owner,indexing_jobs",
    )
