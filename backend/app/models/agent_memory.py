"""Owner-scoped persistent memory records for repository agent tasks."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentMemory(Base):
    __tablename__ = "agent_memories"
    __table_args__ = (
        ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            name="fk_agent_memories_repository_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["task_id", "user_id", "repository_id"],
            ["agent_tasks.id", "agent_tasks.user_id", "agent_tasks.repository_id"],
            name="fk_agent_memories_task_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_execution_id"],
            ["agent_tool_executions.id"],
            name="fk_agent_memories_source_execution",
            ondelete="SET NULL",
        ),
        UniqueConstraint(
            "user_id",
            "repository_id",
            "content_hash",
            name="uq_agent_memories_user_repo_hash",
        ),
        CheckConstraint(
            "memory_type IN ('architecture','convention','decision','troubleshooting','note','observation')",
            name="memory_type_allowed",
        ),
        CheckConstraint("origin IN ('user','agent')", name="origin_allowed"),
        CheckConstraint("importance BETWEEN 1 AND 5", name="importance_valid"),
        CheckConstraint("confidence BETWEEN 0.0 AND 1.0", name="confidence_valid"),
        CheckConstraint("length(title) BETWEEN 3 AND 160", name="title_length_valid"),
        CheckConstraint("length(content) BETWEEN 8 AND 6000", name="content_length_valid"),
        CheckConstraint("access_count >= 0", name="access_count_nonnegative"),
        Index("ix_agent_memories_user_repo_active", "user_id", "repository_id", "is_active"),
        Index("ix_agent_memories_repo_commit", "repository_id", "source_commit_sha"),
        Index("ix_agent_memories_repo_updated", "repository_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    source_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    memory_type: Mapped[str] = mapped_column(String(24), nullable=False)
    origin: Mapped[str] = mapped_column(String(12), nullable=False, default="user")
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    source_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
