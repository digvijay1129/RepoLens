"""GitHub repository records owned by a RepoLens workspace user."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
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
        CheckConstraint(
            "embedding_status IN ('pending', 'embedding', 'embedded', 'failed')",
            name="embedding_status_allowed",
        ),
        CheckConstraint(
            "embedding_dimensions IS NULL OR embedding_dimensions BETWEEN 1 AND 8192",
            name="embedding_dimensions_valid",
        ),
        CheckConstraint("stargazers_count >= 0", name="stargazers_nonnegative"),
        CheckConstraint("forks_count >= 0", name="forks_nonnegative"),
        CheckConstraint("open_issues_count >= 0", name="open_issues_nonnegative"),
        Index("ix_repositories_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    github_repository_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    github_owner: Mapped[str] = mapped_column(String(39), nullable=False)
    github_name: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(140), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stargazers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    forks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    open_issues_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    license_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    github_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_branch: Mapped[str] = mapped_column(
        String(255), nullable=False, default="main", server_default="main"
    )
    indexed_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    indexing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    embedding_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    embedding_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="repositories")
    chunks: Mapped[list["RepositoryChunk"]] = relationship(
        back_populates="repository",
        foreign_keys="[RepositoryChunk.repository_id, RepositoryChunk.user_id]",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    indexing_jobs: Mapped[list["IndexingJob"]] = relationship(
        back_populates="repository",
        foreign_keys="[IndexingJob.repository_id, IndexingJob.user_id]",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="owner,indexing_jobs",
    )
