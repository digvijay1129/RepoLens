"""GitHub repository records owned by a RepoLens workspace user."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("user_id", "full_name", name="uq_repositories_user_full_name"),
        UniqueConstraint("id", "user_id", name="uq_repositories_id_user_id"),
        CheckConstraint(
            "indexing_status IN ('pending', 'indexing', 'indexed', 'failed')",
            name="indexing_status_allowed",
        ),
        CheckConstraint("full_name = lower(full_name)", name="full_name_lowercase"),
        Index("ix_repositories_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    github_owner: Mapped[str] = mapped_column(String(39), nullable=False)
    github_name: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(140), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(300), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    indexed_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    indexing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="repositories")
    indexing_jobs: Mapped[list["IndexingJob"]] = relationship(
        back_populates="repository",
        foreign_keys="[IndexingJob.repository_id, IndexingJob.user_id]",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="owner,indexing_jobs",
    )
