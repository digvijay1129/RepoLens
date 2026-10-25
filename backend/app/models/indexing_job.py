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
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
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
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
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
