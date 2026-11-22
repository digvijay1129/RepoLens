"""Owner-scoped, read-only tools backed by existing RepoLens repository services."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select

from app.agents.tools.registry import AgentToolContext, AgentToolError
from app.models.repository_chunk import RepositoryChunk
from app.services.embeddings import EmbeddingConfigurationError
from app.services.retrieval import SearchReadinessError, search_repository_chunks


class RepositoryOverviewArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListIndexedFilesArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    prefix: str | None = Field(default=None, min_length=1, max_length=512)
    limit: int = Field(default=40, ge=1, le=100)

    @field_validator("prefix")
    @classmethod
    def validate_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value.startswith("/") or "\\" in value or any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("Use a repository-relative directory prefix.")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("The path prefix contains unsupported characters.")
        return value.rstrip("/")


class SearchCodeArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=2, max_length=500)
    mode: Literal["keyword", "semantic", "hybrid"] = "keyword"
    limit: int = Field(default=6, ge=1, le=10)


class InspectSourceArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    file_path: str = Field(min_length=1, max_length=1024)
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    max_lines: int = Field(default=160, ge=1, le=300)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        if value.startswith("/") or "\\" in value or any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("Use an exact repository-relative file path.")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("The file path contains unsupported characters.")
        return value

    @model_validator(mode="after")
    def validate_line_range(self):
        if self.end_line is not None:
            if self.end_line < self.start_line:
                raise ValueError("end_line must be greater than or equal to start_line.")
            if self.end_line - self.start_line + 1 > self.max_lines:
                raise ValueError("The requested line range exceeds max_lines.")
        return self


def _require_indexed_context(context: AgentToolContext) -> str:
    repository = context.repository
    if repository.user_id != context.user_id:
        raise AgentToolError("Saved repository was not found.")
    if repository.indexing_status != "indexed" or not repository.indexed_commit_sha:
        raise AgentToolError("Index the repository before using repository tools.")
    return repository.indexed_commit_sha


async def repository_overview(
    context: AgentToolContext,
    arguments: RepositoryOverviewArguments,
) -> dict:
    commit_sha = _require_indexed_context(context)
    chunks_count, files_count = context.db.execute(
        select(
            func.count(RepositoryChunk.id),
            func.count(func.distinct(RepositoryChunk.file_path)),
        ).where(
            RepositoryChunk.repository_id == context.repository.id,
            RepositoryChunk.user_id == context.user_id,
            RepositoryChunk.commit_sha == commit_sha,
        )
    ).one()
    repository = context.repository
    return {
        "repository": repository.full_name,
        "description": repository.description,
        "primary_language": repository.language,
        "default_branch": repository.default_branch,
        "selected_branch": repository.selected_branch,
        "indexed_commit_sha": commit_sha,
        "indexing_status": repository.indexing_status,
        "embedding_status": repository.embedding_status,
        "indexed_file_count": int(files_count or 0),
        "indexed_chunk_count": int(chunks_count or 0),
        "source_execution": "disabled; indexed source is read-only",
    }


async def list_indexed_files(
    context: AgentToolContext,
    arguments: ListIndexedFilesArguments,
) -> dict:
    commit_sha = _require_indexed_context(context)
    statement = select(
        RepositoryChunk.file_path,
        RepositoryChunk.language,
        func.count(RepositoryChunk.id).label("chunk_count"),
        func.min(RepositoryChunk.start_line).label("start_line"),
        func.max(RepositoryChunk.end_line).label("end_line"),
    ).where(
        RepositoryChunk.repository_id == context.repository.id,
        RepositoryChunk.user_id == context.user_id,
        RepositoryChunk.commit_sha == commit_sha,
    )
    if arguments.prefix:
        statement = statement.where(RepositoryChunk.file_path.startswith(arguments.prefix))
    statement = (
        statement.group_by(RepositoryChunk.file_path, RepositoryChunk.language)
        .order_by(RepositoryChunk.file_path.asc())
        .limit(arguments.limit)
    )
    rows = context.db.execute(statement).all()
    return {
        "repository": context.repository.full_name,
        "commit_sha": commit_sha,
        "files": [
            {
                "file_path": row.file_path,
                "language": row.language,
                "chunk_count": int(row.chunk_count),
                "start_line": int(row.start_line),
                "end_line": int(row.end_line),
            }
            for row in rows
        ],
        "result_count": len(rows),
        "limit": arguments.limit,
    }


async def search_code(
    context: AgentToolContext,
    arguments: SearchCodeArguments,
) -> dict:
    _require_indexed_context(context)
    try:
        result = await search_repository_chunks(
            context.db,
            context.repository,
            context.user_id,
            arguments.query,
            mode=arguments.mode,
            limit=arguments.limit,
        )
    except (SearchReadinessError, EmbeddingConfigurationError) as exc:
        raise AgentToolError(str(exc)) from exc
    return {
        "repository": result.get("repository", context.repository.full_name),
        "commit_sha": result.get("commit_sha", context.repository.indexed_commit_sha),
        "query": arguments.query,
        "mode": arguments.mode,
        "result_count": result.get("result_count", len(result.get("results", []))),
        "results": [
            {
                **item,
                "chunk_id": str(item["chunk_id"]),
            }
            for item in result.get("results", [])[: arguments.limit]
        ],
    }


async def inspect_source(
    context: AgentToolContext,
    arguments: InspectSourceArguments,
) -> dict:
    commit_sha = _require_indexed_context(context)
    end_line = arguments.end_line or (arguments.start_line + arguments.max_lines - 1)
    chunks = context.db.scalars(
        select(RepositoryChunk)
        .where(
            RepositoryChunk.repository_id == context.repository.id,
            RepositoryChunk.user_id == context.user_id,
            RepositoryChunk.commit_sha == commit_sha,
            RepositoryChunk.file_path == arguments.file_path,
            RepositoryChunk.end_line >= arguments.start_line,
            RepositoryChunk.start_line <= end_line,
        )
        .order_by(RepositoryChunk.chunk_index.asc())
    ).all()
    if not chunks:
        raise AgentToolError("The requested file or line range was not found in the indexed snapshot.")

    source_lines: dict[int, str] = {}
    for chunk in chunks:
        raw_lines = chunk.chunk_text.splitlines()
        for offset, line in enumerate(raw_lines):
            line_number = chunk.start_line + offset
            if line_number > chunk.end_line or line_number < arguments.start_line or line_number > end_line:
                continue
            source_lines.setdefault(line_number, line)

    selected = sorted(source_lines.items())[: arguments.max_lines]
    return {
        "repository": context.repository.full_name,
        "commit_sha": commit_sha,
        "file_path": arguments.file_path,
        "requested_start_line": arguments.start_line,
        "requested_end_line": end_line,
        "returned_line_count": len(selected),
        "source": "\n".join(f"{line_number}: {line}" for line_number, line in selected),
        "citation_url": (
            f"https://github.com/{context.repository.github_owner}/"
            f"{context.repository.github_name}/blob/{commit_sha}/"
            f"{arguments.file_path}#L{arguments.start_line}-L{end_line}"
        ),
    }
