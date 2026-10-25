"""Owner-scoped semantic, keyword, and hybrid retrieval over indexed source chunks."""

from __future__ import annotations

import math
import re
import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from sqlalchemy import func, select, literal_column
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.repository import Repository
from app.models.repository_chunk import RepositoryChunk
from app.models.repository_chunk_embedding import RepositoryChunkEmbedding
from app.services.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    OpenAICompatibleEmbeddingProvider,
    get_embedding_configuration,
)


class SearchReadinessError(RuntimeError):
    """Raised when a repository is not ready for the requested retrieval mode."""


def _lexical_terms(value: str) -> list[str]:
    return [part.casefold() for part in re.findall(r"[A-Za-z0-9_.$-]+", value) if len(part) > 1]


def _cosine_distance(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 2.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 2.0
    return 1.0 - (dot / (left_norm * right_norm))


def _keyword_candidates(
    db: Session,
    repository: Repository,
    user_id: uuid.UUID,
    query: str,
    candidate_limit: int,
) -> list[tuple[RepositoryChunk, float]]:
    filters = (
        RepositoryChunk.repository_id == repository.id,
        RepositoryChunk.user_id == user_id,
        RepositoryChunk.commit_sha == repository.indexed_commit_sha,
    )
    if db.get_bind().dialect.name == "postgresql":
        document = func.to_tsvector(literal_column("'simple'"), RepositoryChunk.chunk_text)
        query_vector = func.plainto_tsquery(literal_column("'simple'"), query)
        rank = func.ts_rank_cd(document, query_vector)
        statement = (
            select(RepositoryChunk, rank.label("keyword_rank"))
            .where(*filters, document.op("@@")(query_vector))
            .order_by(rank.desc(), RepositoryChunk.file_path, RepositoryChunk.chunk_index)
            .limit(candidate_limit)
        )
        return [(row[0], float(row[1] or 0.0)) for row in db.execute(statement).all()]

    # Lightweight compatibility path for isolated SQLite tests; production uses
    # PostgreSQL full-text search with the GIN expression index.
    terms = _lexical_terms(query)
    if not terms:
        return []
    chunks = db.scalars(
        select(RepositoryChunk).where(*filters)
    ).all()
    scored: list[tuple[RepositoryChunk, float]] = []
    for chunk in chunks:
        content = chunk.chunk_text.casefold()
        count = sum(content.count(term) for term in terms)
        if count:
            score = count / max(1.0, float(len(terms)))
            scored.append((chunk, score))
    scored.sort(key=lambda item: (-item[1], item[0].file_path, item[0].chunk_index))
    return scored[:candidate_limit]


def _semantic_candidates(
    db: Session,
    repository: Repository,
    user_id: uuid.UUID,
    query_vector: list[float],
    candidate_limit: int,
) -> list[tuple[RepositoryChunk, float]]:
    provider = repository.embedding_provider
    model = repository.embedding_model
    dimensions = repository.embedding_dimensions
    commit_sha = repository.indexed_commit_sha
    if not provider or not model or not dimensions or not commit_sha:
        raise SearchReadinessError("Generate embeddings for the current indexed source before semantic search.")

    filters = (
        RepositoryChunkEmbedding.user_id == user_id,
        RepositoryChunkEmbedding.repository_id == repository.id,
        RepositoryChunkEmbedding.commit_sha == commit_sha,
        RepositoryChunkEmbedding.provider == provider,
        RepositoryChunkEmbedding.model == model,
        RepositoryChunkEmbedding.dimensions == dimensions,
        RepositoryChunkEmbedding.content_hash == RepositoryChunk.content_hash,
        RepositoryChunk.user_id == user_id,
        RepositoryChunk.repository_id == repository.id,
        RepositoryChunk.commit_sha == commit_sha,
    )
    if db.get_bind().dialect.name == "postgresql":
        distance = RepositoryChunkEmbedding.vector.cosine_distance(query_vector)
        statement = (
            select(RepositoryChunk, distance.label("cosine_distance"))
            .join(RepositoryChunkEmbedding, RepositoryChunkEmbedding.chunk_id == RepositoryChunk.id)
            .where(*filters)
            .order_by(distance.asc(), RepositoryChunk.file_path, RepositoryChunk.chunk_index)
            .limit(candidate_limit)
        )
        return [(row[0], float(row[1])) for row in db.execute(statement).all()]

    rows = db.execute(
        select(RepositoryChunk, RepositoryChunkEmbedding.vector)
        .join(RepositoryChunkEmbedding, RepositoryChunkEmbedding.chunk_id == RepositoryChunk.id)
        .where(*filters)
    ).all()
    scored = [
        (row[0], _cosine_distance(list(row[1]), query_vector))
        for row in rows
        if row[1] is not None and len(row[1]) == len(query_vector)
    ]
    scored.sort(key=lambda item: (item[1], item[0].file_path, item[0].chunk_index))
    return scored[:candidate_limit]


def _citation_url(repository: Repository, commit_sha: str, file_path: str, start_line: int, end_line: int) -> str:
    owner = quote(repository.github_owner, safe="")
    name = quote(repository.github_name, safe="")
    path = quote(file_path, safe="/")
    return (
        f"https://github.com/{owner}/{name}/blob/{commit_sha}/{path}"
        f"#L{start_line}-L{end_line}"
    )


def _result_payload(repository: Repository, chunk: RepositoryChunk, score: float, matches: list[str]) -> dict[str, Any]:
    commit_sha = chunk.commit_sha
    return {
        "chunk_id": chunk.id,
        "file_path": chunk.file_path,
        "language": chunk.language,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "symbol_names": [name.strip() for name in chunk.symbol_names.split(",") if name.strip()],
        "snippet": chunk.chunk_text[:1200],
        "score": round(max(0.0, min(1.0, score)), 6),
        "match_types": matches,
        "commit_sha": commit_sha,
        "citation_url": _citation_url(repository, commit_sha, chunk.file_path, chunk.start_line, chunk.end_line),
    }


async def search_repository_chunks(
    db: Session,
    repository: Repository,
    user_id: uuid.UUID,
    query: str,
    *,
    mode: str = "hybrid",
    limit: int = 8,
    embedding_settings_factory: Callable[[], Settings] | None = None,
    embedding_provider_factory: Callable[[Settings], Any] | None = None,
) -> dict[str, Any]:
    """Search only the signed-in user's current indexed snapshot with citations."""
    query = query.strip()
    mode = mode.lower()
    if mode not in {"keyword", "semantic", "hybrid"}:
        raise ValueError("Search mode must be keyword, semantic, or hybrid.")
    if not 2 <= len(query) <= 500:
        raise ValueError("Search query must contain 2 to 500 characters.")
    if not 1 <= limit <= 20:
        raise ValueError("Search result limit must be between 1 and 20.")
    if repository.user_id != user_id:
        raise SearchReadinessError("Saved repository was not found.")
    if repository.indexing_status != "indexed" or not repository.indexed_commit_sha:
        raise SearchReadinessError("Index source files before searching this repository.")

    # A generous bounded candidate pool makes RRF more resilient when exact file
    # identifiers rank highly in keyword search but related source is semantic.
    candidate_limit = max(30, min(100, limit * 5))
    keyword = (
        _keyword_candidates(db, repository, user_id, query, candidate_limit)
        if mode in {"keyword", "hybrid"}
        else []
    )
    semantic: list[tuple[RepositoryChunk, float]] = []
    if mode in {"semantic", "hybrid"}:
        settings = (
            embedding_settings_factory()
            if embedding_settings_factory is not None
            else get_embedding_configuration()
        )
        if (
            repository.embedding_status != "embedded"
            or repository.embedding_provider != settings.embeddings_provider.strip().lower()
            or repository.embedding_model != settings.embeddings_model.strip()
            or repository.embedding_dimensions != settings.embeddings_dimensions
        ):
            raise SearchReadinessError(
                "The current embedding model does not match this repository's active vectors. "
                "Regenerate embeddings with the active provider/model, then try again."
            )
        provider_factory = embedding_provider_factory or (
            lambda supplied_settings: OpenAICompatibleEmbeddingProvider(supplied_settings)
        )
        async with provider_factory(settings) as provider:
            query_vectors = await provider.embed_texts([query])
        if len(query_vectors) != 1 or len(query_vectors[0]) != settings.embeddings_dimensions:
            raise EmbeddingProviderError("The embedding provider returned an invalid query vector.")
        semantic = _semantic_candidates(
            db, repository, user_id, query_vectors[0], candidate_limit
        )

    chunks: dict[uuid.UUID, RepositoryChunk] = {}
    semantic_scores: dict[uuid.UUID, float] = {}
    keyword_scores: dict[uuid.UUID, float] = {}
    semantic_order: list[uuid.UUID] = []
    keyword_order: list[uuid.UUID] = []
    for rank, (chunk, distance) in enumerate(semantic, start=1):
        chunks[chunk.id] = chunk
        semantic_scores[chunk.id] = max(0.0, min(1.0, 1.0 - distance))
        semantic_order.append(chunk.id)
    for rank, (chunk, score) in enumerate(keyword, start=1):
        chunks[chunk.id] = chunk
        keyword_scores[chunk.id] = score
        keyword_order.append(chunk.id)

    matches: dict[uuid.UUID, list[str]] = defaultdict(list)
    for chunk_id in semantic_order:
        matches[chunk_id].append("semantic")
    for chunk_id in keyword_order:
        matches[chunk_id].append("keyword")

    if mode == "semantic":
        ordered_ids = semantic_order
        scores = semantic_scores
    elif mode == "keyword":
        ordered_ids = keyword_order
        max_keyword = max(keyword_scores.values(), default=0.0)
        scores = {
            chunk_id: (value / max_keyword if max_keyword > 0 else 0.0)
            for chunk_id, value in keyword_scores.items()
        }
    else:
        fused: dict[uuid.UUID, float] = defaultdict(float)
        for rank, chunk_id in enumerate(semantic_order, start=1):
            fused[chunk_id] += 1.0 / (60.0 + rank)
        for rank, chunk_id in enumerate(keyword_order, start=1):
            fused[chunk_id] += 1.0 / (60.0 + rank)
        ordered_ids = sorted(
            fused,
            key=lambda chunk_id: (-fused[chunk_id], chunks[chunk_id].file_path, chunks[chunk_id].chunk_index),
        )
        max_fused = max(fused.values(), default=0.0)
        scores = {chunk_id: fused[chunk_id] / max_fused for chunk_id in fused}

    results = [
        _result_payload(repository, chunks[chunk_id], scores.get(chunk_id, 0.0), matches[chunk_id])
        for chunk_id in ordered_ids[:limit]
    ]
    return {
        "repository_id": repository.id,
        "repository": repository.full_name,
        "query": query,
        "mode": mode,
        "commit_sha": repository.indexed_commit_sha,
        "result_count": len(results),
        "results": results,
    }
