"""Scoped repository memory capture, retrieval and lifecycle operations."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent_memory import AgentMemory
from app.models.agent_step import AgentStep
from app.models.agent_task import AgentTask
from app.models.agent_tool_execution import AgentToolExecution
from app.models.repository import Repository


MAX_ACTIVE_MEMORIES_PER_REPOSITORY = 250
MAX_AUTO_MEMORY_CONTENT = 1800
AUTO_MEMORY_TTL_DAYS = 30


class AgentMemoryNotFoundError(RuntimeError):
    """Raised when a repository memory is not visible to the current owner."""


class AgentMemoryLimitError(RuntimeError):
    """Raised when the repository memory quota has been reached."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _content_hash(memory_type: str, content: str) -> str:
    normalized = re.sub(r"\s+", " ", content).strip().casefold()
    return hashlib.sha256(f"{memory_type.casefold()}\n{normalized}".encode("utf-8")).hexdigest()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9_./+-]{2,}", value.casefold())
        if token not in {"the", "and", "for", "with", "from", "this", "that", "into"}
    }


def serialize_memory(
    memory: AgentMemory,
    *,
    relevance: float | None = None,
    current_commit_sha: str | None = None,
) -> dict[str, Any]:
    data = {
        "id": str(memory.id),
        "repository_id": str(memory.repository_id),
        "task_id": str(memory.task_id) if memory.task_id else None,
        "source_execution_id": str(memory.source_execution_id) if memory.source_execution_id else None,
        "memory_type": memory.memory_type,
        "origin": memory.origin,
        "title": memory.title,
        "content": memory.content,
        "tags": memory.tags or [],
        "source_refs": memory.source_refs or [],
        "source_commit_sha": memory.source_commit_sha,
        "confidence": memory.confidence,
        "importance": memory.importance,
        "is_active": memory.is_active,
        "access_count": memory.access_count,
        "last_accessed_at": memory.last_accessed_at.isoformat() if memory.last_accessed_at else None,
        "expires_at": memory.expires_at.isoformat() if memory.expires_at else None,
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
    }
    if relevance is not None:
        data["relevance_score"] = round(relevance, 4)
        data["snapshot_matches"] = (
            None
            if current_commit_sha is None
            else memory.source_commit_sha is None or memory.source_commit_sha == current_commit_sha
        )
    return data


def _ensure_repository(db: Session, *, repository_id: uuid.UUID, user_id: uuid.UUID) -> Repository:
    repository = db.scalar(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == user_id,
        )
    )
    if repository is None:
        raise AgentMemoryNotFoundError("Saved repository was not found.")
    return repository


def _memory_score(
    memory: AgentMemory,
    *,
    query_tokens: set[str],
    query_text: str,
    current_commit_sha: str | None,
) -> float:
    title_tokens = _tokens(memory.title)
    content_tokens = _tokens(memory.content)
    tag_tokens = _tokens(" ".join(memory.tags or []))
    matched = query_tokens & (title_tokens | content_tokens | tag_tokens)
    if not matched:
        return 0.0
    score = (
        2.5 * len(query_tokens & title_tokens)
        + 1.0 * len(query_tokens & content_tokens)
        + 1.8 * len(query_tokens & tag_tokens)
    ) / max(1.0, len(query_tokens) ** 0.65)
    haystack = f"{memory.title} {memory.content}".casefold()
    if len(query_text) >= 5 and query_text.casefold() in haystack:
        score += 2.0
    score *= 0.7 + (memory.importance * 0.1)
    score *= max(0.25, min(1.0, memory.confidence))
    if memory.source_commit_sha and current_commit_sha and memory.source_commit_sha != current_commit_sha:
        score *= 0.65
    updated_at = memory.updated_at or memory.created_at or _utcnow()
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (_utcnow() - updated_at).total_seconds() / 86400)
    score *= max(0.65, 1.0 - (age_days / 365.0) * 0.35)
    return score


def retrieve_relevant_memories(
    db: Session,
    *,
    repository_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    current_commit_sha: str | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Retrieve active memories from exactly one owner's repository scope."""
    query = query.strip()[:1200]
    query_tokens = _tokens(query)
    if len(query_tokens) < 1:
        return []
    now = _utcnow()
    candidates = db.scalars(
        select(AgentMemory)
        .where(
            AgentMemory.repository_id == repository_id,
            AgentMemory.user_id == user_id,
            AgentMemory.is_active.is_(True),
            (AgentMemory.expires_at.is_(None) | (AgentMemory.expires_at > now)),
        )
        .order_by(AgentMemory.importance.desc(), AgentMemory.updated_at.desc())
        .limit(1000)
    ).all()
    ranked = [
        (memory, _memory_score(
            memory,
            query_tokens=query_tokens,
            query_text=query,
            current_commit_sha=current_commit_sha,
        ))
        for memory in candidates
    ]
    ranked = sorted(
        ((memory, score) for memory, score in ranked if score > 0),
        key=lambda item: (item[1], item[0].updated_at),
        reverse=True,
    )[: max(1, min(limit, 12))]
    if ranked:
        for memory, _score in ranked:
            memory.access_count += 1
            memory.last_accessed_at = now
        db.commit()
    return [
        serialize_memory(memory, relevance=score, current_commit_sha=current_commit_sha)
        for memory, score in ranked
    ]


def list_repository_memories(
    db: Session,
    *,
    repository_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str | None = None,
    memory_type: str | None = None,
    include_inactive: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    _ensure_repository(db, repository_id=repository_id, user_id=user_id)
    now = _utcnow()
    statement = select(AgentMemory).where(
        AgentMemory.repository_id == repository_id,
        AgentMemory.user_id == user_id,
    )
    if not include_inactive:
        statement = statement.where(
            AgentMemory.is_active.is_(True),
            AgentMemory.expires_at.is_(None) | (AgentMemory.expires_at > now),
        )
    if memory_type:
        statement = statement.where(AgentMemory.memory_type == memory_type)
    memories = db.scalars(
        statement.order_by(AgentMemory.updated_at.desc()).limit(max(1, min(limit, 100)))
    ).all()
    if query and query.strip():
        tokens = _tokens(query)
        memories = sorted(
            (
                (memory, _memory_score(
                    memory,
                    query_tokens=tokens,
                    query_text=query.strip(),
                    current_commit_sha=None,
                ))
                for memory in memories
            ),
            key=lambda item: (item[1], item[0].updated_at),
            reverse=True,
        )
        return [serialize_memory(memory, relevance=score) for memory, score in memories if score > 0]
    return [serialize_memory(memory) for memory in memories]


def create_repository_memory(
    db: Session,
    *,
    repository_id: uuid.UUID,
    user_id: uuid.UUID,
    memory_type: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
    importance: int = 3,
    confidence: float = 1.0,
    source_commit_sha: str | None = None,
    task_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    repository = _ensure_repository(db, repository_id=repository_id, user_id=user_id)
    if task_id is not None:
        task = db.scalar(
            select(AgentTask).where(
                AgentTask.id == task_id,
                AgentTask.user_id == user_id,
                AgentTask.repository_id == repository_id,
            )
        )
        if task is None:
            raise AgentMemoryNotFoundError("Agent task was not found in this repository.")
    normalized_tags = list(dict.fromkeys(
        tag.strip().casefold()[:48] for tag in (tags or []) if tag.strip()
    ))[:12]
    normalized_content = content.strip()
    digest = _content_hash(memory_type, normalized_content)
    existing = db.scalar(
        select(AgentMemory).where(
            AgentMemory.user_id == user_id,
            AgentMemory.repository_id == repository_id,
            AgentMemory.content_hash == digest,
        )
    )
    if existing is not None:
        existing.origin = "user"
        existing.title = title.strip()
        existing.content = normalized_content
        existing.tags = normalized_tags
        existing.importance = importance
        existing.confidence = confidence
        existing.source_commit_sha = source_commit_sha or existing.source_commit_sha
        existing.task_id = task_id or existing.task_id
        existing.is_active = True
        existing.expires_at = expires_at
        existing.updated_at = _utcnow()
        db.commit()
        db.refresh(existing)
        return serialize_memory(existing)

    active_count = int(
        db.scalar(
            select(func.count(AgentMemory.id)).where(
                AgentMemory.user_id == user_id,
                AgentMemory.repository_id == repository_id,
                AgentMemory.is_active.is_(True),
                (AgentMemory.expires_at.is_(None) | (AgentMemory.expires_at > _utcnow())),
            )
        ) or 0
    )
    if active_count >= MAX_ACTIVE_MEMORIES_PER_REPOSITORY:
        raise AgentMemoryLimitError(
            f"This repository has reached its {MAX_ACTIVE_MEMORIES_PER_REPOSITORY}-memory active limit."
        )
    memory = AgentMemory(
        user_id=user_id,
        repository_id=repository_id,
        task_id=task_id,
        memory_type=memory_type,
        origin="user",
        title=title.strip(),
        content=normalized_content,
        tags=normalized_tags,
        source_refs=[],
        source_commit_sha=source_commit_sha or repository.indexed_commit_sha,
        content_hash=digest,
        confidence=confidence,
        importance=importance,
        expires_at=expires_at,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return serialize_memory(memory)


def update_repository_memory(
    db: Session,
    *,
    memory_id: uuid.UUID,
    user_id: uuid.UUID,
    updates: dict[str, Any],
) -> dict[str, Any]:
    memory = db.scalar(
        select(AgentMemory).where(
            AgentMemory.id == memory_id,
            AgentMemory.user_id == user_id,
        ).with_for_update()
    )
    if memory is None:
        raise AgentMemoryNotFoundError("Repository memory was not found.")
    allowed = {"memory_type", "title", "content", "tags", "importance", "confidence", "expires_at"}
    for key, value in updates.items():
        if key in allowed and (value is not None or key == "expires_at"):
            if key == "tags":
                value = list(dict.fromkeys(tag.strip().casefold()[:48] for tag in value if tag.strip()))[:12]
            setattr(memory, key, value)
    updated_hash = _content_hash(memory.memory_type, memory.content)
    duplicate = db.scalar(
        select(AgentMemory).where(
            AgentMemory.user_id == memory.user_id,
            AgentMemory.repository_id == memory.repository_id,
            AgentMemory.content_hash == updated_hash,
            AgentMemory.id != memory.id,
        )
    )
    if duplicate is not None:
        raise AgentMemoryLimitError("Another memory with the same content already exists.")
    memory.content_hash = updated_hash
    memory.updated_at = _utcnow()
    db.commit()
    db.refresh(memory)
    return serialize_memory(memory)


def delete_repository_memory(
    db: Session,
    *,
    memory_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    memory = db.scalar(
        select(AgentMemory).where(
            AgentMemory.id == memory_id,
            AgentMemory.user_id == user_id,
        ).with_for_update()
    )
    if memory is None:
        raise AgentMemoryNotFoundError("Repository memory was not found.")
    db.delete(memory)
    db.commit()


def capture_tool_execution_memory(
    db: Session,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
    execution_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Save a compact metadata/reference observation; never persist source excerpts."""
    task = db.scalar(
        select(AgentTask).where(
            AgentTask.id == task_id,
            AgentTask.user_id == user_id,
        )
    )
    if task is None:
        return None
    execution = db.scalar(
        select(AgentToolExecution).where(
            AgentToolExecution.id == execution_id,
            AgentToolExecution.task_id == task_id,
            AgentToolExecution.user_id == user_id,
            AgentToolExecution.repository_id == task.repository_id,
            AgentToolExecution.status == "succeeded",
        )
    )
    if execution is None:
        return None
    repository = db.scalar(
        select(Repository).where(
            Repository.id == task.repository_id,
            Repository.user_id == user_id,
        )
    )
    step = db.scalar(
        select(AgentStep).where(
            AgentStep.id == execution.step_id,
            AgentStep.task_id == task_id,
            AgentStep.user_id == user_id,
            AgentStep.repository_id == task.repository_id,
        )
    )
    if repository is None or step is None:
        return None
    output = execution.tool_output or {}
    refs: list[dict[str, Any]] = []
    if execution.tool_name == "repository_overview":
        content = (
            f"Repository {repository.full_name} was inspected at indexed commit "
            f"{task.indexed_commit_sha}. Primary language: {output.get('primary_language') or 'not reported'}. "
            f"Indexed files: {output.get('indexed_file_count', 0)}; chunks: {output.get('indexed_chunk_count', 0)}."
        )
        memory_type = "architecture"
        tags = ["repository-overview", "index-metadata", str(output.get("primary_language") or "unknown")]
        importance = 3
    elif execution.tool_name == "search_code":
        query = str(output.get("query") or execution.tool_input.get("arguments", {}).get("query") or "")[:240]
        results = output.get("results") or []
        paths = list(dict.fromkeys(
            str(item.get("file_path"))
            for item in results[:12]
            if isinstance(item, dict) and item.get("file_path")
        ))
        content = (
            f"Repository search for '{query}' returned {output.get('result_count', len(results))} result(s). "
            f"Relevant indexed files: {', '.join(paths) if paths else 'no file paths returned'}. "
            "This memory stores search provenance only, not source-code excerpts."
        )
        memory_type = "observation"
        tags = ["code-search", *[path.rsplit("/", 1)[-1] for path in paths[:5]]]
        importance = 2
        refs = [
            {
                "file_path": str(item["file_path"]),
                "start_line": item.get("start_line"),
                "end_line": item.get("end_line"),
                "citation_url": item.get("citation_url"),
            }
            for item in results[:12]
            if isinstance(item, dict) and item.get("file_path")
        ]
    elif execution.tool_name == "inspect_source":
        file_path = str(output.get("file_path") or execution.tool_input.get("arguments", {}).get("file_path") or "")[:500]
        citation = output.get("citation_url")
        content = (
            f"Source evidence for step '{step.title[:120]}' was inspected in {file_path} "
            f"(lines {output.get('requested_start_line', 1)}–{output.get('requested_end_line', '?')}). "
            "The original source excerpt is intentionally not copied into memory."
        )
        memory_type = "observation"
        tags = ["source-inspection", file_path.rsplit("/", 1)[-1]]
        importance = 2
        if citation:
            refs = [{"file_path": file_path, "citation_url": str(citation)[:1000]}]
    elif execution.tool_name == "list_indexed_files":
        files = output.get("files") or []
        prefix = execution.tool_input.get("arguments", {}).get("prefix") or "repository root"
        paths = [str(item["file_path"]) for item in files[:15] if isinstance(item, dict) and item.get("file_path")]
        content = (
            f"An indexed-file inventory for {prefix} returned {output.get('result_count', len(files))} path(s). "
            f"Sample paths: {', '.join(paths) if paths else 'none returned'}."
        )
        memory_type = "observation"
        tags = ["file-inventory", str(prefix)[:48]]
        importance = 1
    else:
        return None

    content = content[:MAX_AUTO_MEMORY_CONTENT]
    digest = _content_hash(memory_type, content)
    existing = db.scalar(
        select(AgentMemory).where(
            AgentMemory.user_id == user_id,
            AgentMemory.repository_id == repository.id,
            AgentMemory.content_hash == digest,
        )
    )
    now = _utcnow()
    if existing is not None:
        existing.task_id = task.id
        existing.source_execution_id = execution.id
        existing.source_commit_sha = task.indexed_commit_sha
        existing.source_refs = refs
        existing.updated_at = now
        existing.expires_at = now + timedelta(days=AUTO_MEMORY_TTL_DAYS)
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return serialize_memory(existing)

    active_count = int(
        db.scalar(
            select(func.count(AgentMemory.id)).where(
                AgentMemory.user_id == user_id,
                AgentMemory.repository_id == repository.id,
                AgentMemory.is_active.is_(True),
                (AgentMemory.expires_at.is_(None) | (AgentMemory.expires_at > now)),
            )
        ) or 0
    )
    if active_count >= MAX_ACTIVE_MEMORIES_PER_REPOSITORY:
        return None
    memory = AgentMemory(
        user_id=user_id,
        repository_id=repository.id,
        task_id=task.id,
        source_execution_id=execution.id,
        memory_type=memory_type,
        origin="agent",
        title=f"{execution.tool_name}: {step.title}"[:160],
        content=content,
        tags=list(dict.fromkeys(tag.casefold()[:48] for tag in tags))[:12],
        source_refs=refs,
        source_commit_sha=task.indexed_commit_sha,
        content_hash=digest,
        confidence=0.75,
        importance=importance,
        expires_at=now + timedelta(days=AUTO_MEMORY_TTL_DAYS),
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return serialize_memory(memory)
