"""Background indexing pipeline for public GitHub repositories.

The worker only reads bounded UTF-8 text files, chunks them deterministically, and
persists snapshots. It never imports or executes source from the indexed repository.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_engine
from app.models.indexing_job import IndexingJob
from app.models.repository import Repository
from app.models.repository_chunk import RepositoryChunk
from app.services.github_client import GitHubClientError, GitHubPublicClient
from app.services.source_ingestion import get_blob_text, get_commit_tree
from app.services.source_parser import chunk_source_text, is_indexable_path

logger = logging.getLogger(__name__)

MAX_INDEX_FILES = 40
MAX_INDEX_FILE_BYTES = 256 * 1024
MAX_INDEX_TOTAL_BYTES = 5 * 1024 * 1024
PROGRESS_COMMIT_EVERY_FILES = 1


class IndexingPipelineError(RuntimeError):
    """Safe, user-displayable indexing error."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _count_chunks(db: Session, repository_id: uuid.UUID, user_id: uuid.UUID, commit_sha: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(RepositoryChunk)
            .where(
                RepositoryChunk.repository_id == repository_id,
                RepositoryChunk.user_id == user_id,
                RepositoryChunk.commit_sha == commit_sha,
            )
        )
        or 0
    )


def _fail_job(
    db: Session,
    job_id: uuid.UUID,
    *,
    prior_commit_sha: str | None,
    prior_status: str,
    safe_message: str,
) -> None:
    """Record a safe error while preserving the last completed snapshot."""
    db.rollback()
    job = db.get(IndexingJob, job_id)
    if job is None:
        return
    repository = db.scalar(
        select(Repository).where(
            Repository.id == job.repository_id,
            Repository.user_id == job.user_id,
        )
    )
    attempted_sha = job.commit_sha
    if repository is not None:
        if attempted_sha and (attempted_sha != prior_commit_sha or prior_status != "indexed"):
            db.execute(
                delete(RepositoryChunk).where(
                    RepositoryChunk.repository_id == repository.id,
                    RepositoryChunk.user_id == repository.user_id,
                    RepositoryChunk.commit_sha == attempted_sha,
                )
            )
        repository.indexing_status = "indexed" if prior_commit_sha and prior_status == "indexed" else "failed"

    job.status = "failed"
    job.error_message = safe_message[:1000]
    job.progress_message = "Indexing failed. The previous completed snapshot was preserved."
    job.finished_at = _now()
    db.commit()


async def run_indexing_job(
    job_id: uuid.UUID | str,
    *,
    session_factory: Callable[[], Session] | None = None,
    github_client_factory: Callable[[], Any] | None = None,
) -> None:
    """Execute one queued indexing job. Intended for FastAPI BackgroundTasks."""
    try:
        normalized_job_id = job_id if isinstance(job_id, uuid.UUID) else uuid.UUID(str(job_id))
    except (ValueError, TypeError, AttributeError):
        return

    factory = session_factory or sessionmaker(bind=get_engine(), expire_on_commit=False)
    client_factory = github_client_factory or GitHubPublicClient

    with factory() as db:
        job = db.get(IndexingJob, normalized_job_id)
        if job is None or job.status != "queued":
            return

        repository = db.scalar(
            select(Repository).where(
                Repository.id == job.repository_id,
                Repository.user_id == job.user_id,
            )
        )
        if repository is None:
            job.status = "failed"
            job.error_message = "The saved repository was not found."
            job.progress_message = "Indexing failed."
            job.finished_at = _now()
            db.commit()
            return

        prior_commit_sha = repository.indexed_commit_sha
        prior_status = repository.indexing_status
        job.status = "running"
        job.attempt_count += 1
        job.started_at = _now()
        job.finished_at = None
        job.error_message = None
        job.progress_message = "Resolving the selected GitHub branch."
        repository.indexing_status = "indexing"
        db.commit()

        try:
            async with client_factory() as github:
                owner = repository.github_owner
                name = repository.github_name
                branches = await github.list_branches(owner, name)
                selected_branch = next(
                    (branch for branch in branches if branch.get("name") == repository.selected_branch),
                    None,
                )
                if selected_branch is None or not isinstance(selected_branch.get("commit_sha"), str):
                    raise IndexingPipelineError(
                        "The selected branch was not found in the public GitHub branch list."
                    )
                commit_sha = selected_branch["commit_sha"]
                if not re.fullmatch(r"[0-9a-fA-F]{40}", commit_sha):
                    raise IndexingPipelineError("GitHub returned an invalid commit reference.")

                job.commit_sha = commit_sha
                job.progress_message = "Reading the repository tree."
                db.commit()

                # No unnecessary API calls or duplicate chunks when this exact commit
                # has already been indexed successfully.
                if prior_commit_sha == commit_sha and prior_status == "indexed":
                    existing_chunks = _count_chunks(db, repository.id, repository.user_id, commit_sha)
                    existing_files = int(
                        db.scalar(
                            select(func.count(func.distinct(RepositoryChunk.file_path))).where(
                                RepositoryChunk.repository_id == repository.id,
                                RepositoryChunk.user_id == repository.user_id,
                                RepositoryChunk.commit_sha == commit_sha,
                            )
                        )
                        or 0
                    )
                    job.status = "completed"
                    job.total_files = existing_files
                    job.processed_files = existing_files
                    job.skipped_files = 0
                    job.chunk_count = existing_chunks
                    job.progress_message = "This commit is already indexed; no source changes were needed."
                    job.finished_at = _now()
                    repository.indexing_status = "indexed"
                    db.commit()
                    return

                tree = await get_commit_tree(github, owner, name, commit_sha)
                blob_entries = [entry for entry in tree if entry.get("type") == "blob"]
                candidates: list[dict[str, Any]] = []
                skipped_files = 0

                for entry in blob_entries:
                    path = entry.get("path")
                    size = entry.get("size")
                    if (
                        not isinstance(path, str)
                        or entry.get("mode") == "120000"
                        or not is_indexable_path(path)
                    ):
                        skipped_files += 1
                        continue
                    if not isinstance(size, int) or size < 0 or size > MAX_INDEX_FILE_BYTES:
                        skipped_files += 1
                        continue
                    candidates.append(entry)

                candidates.sort(key=lambda entry: str(entry["path"]).casefold())
                total_size = 0
                bounded_candidates: list[dict[str, Any]] = []
                for entry in candidates:
                    size = int(entry["size"])
                    if len(bounded_candidates) >= MAX_INDEX_FILES:
                        skipped_files += 1
                        continue
                    if total_size + size > MAX_INDEX_TOTAL_BYTES:
                        skipped_files += 1
                        continue
                    bounded_candidates.append(entry)
                    total_size += size

                job.total_files = len(bounded_candidates)
                job.processed_files = 0
                job.skipped_files = skipped_files
                job.chunk_count = 0
                job.progress_message = (
                    f"Found {len(bounded_candidates)} candidate files; applying size and file-type limits."
                )
                db.commit()

                processed = 0
                chunk_count = 0
                actual_source_bytes = 0
                for entry in bounded_candidates:
                    path = str(entry["path"])
                    try:
                        source_text = await get_blob_text(
                            github, owner, name, str(entry["sha"]), max_bytes=MAX_INDEX_FILE_BYTES
                        )
                    except GitHubClientError as exc:
                        if exc.status_code in {413, 415}:
                            skipped_files += 1
                            processed += 1
                            job.processed_files = processed
                            job.skipped_files = skipped_files
                            job.progress_message = f"Skipped unsupported text file ({processed}/{len(bounded_candidates)})."
                            db.commit()
                            continue
                        raise

                    actual_size = len(source_text.encode("utf-8"))
                    if actual_source_bytes + actual_size > MAX_INDEX_TOTAL_BYTES:
                        skipped_files += 1
                        processed += 1
                        job.processed_files = processed
                        job.skipped_files = skipped_files
                        job.progress_message = f"Skipped {path}: total source byte limit reached."
                        db.commit()
                        continue
                    actual_source_bytes += actual_size

                    pieces = chunk_source_text(path, source_text)
                    if not pieces:
                        skipped_files += 1
                    else:
                        rows: list[RepositoryChunk] = []
                        for piece in pieces:
                            text = str(piece["chunk_text"])
                            rows.append(
                                RepositoryChunk(
                                    repository_id=repository.id,
                                    user_id=repository.user_id,
                                    commit_sha=commit_sha,
                                    file_path=path,
                                    language=str(piece["language"]),
                                    chunk_index=int(piece["chunk_index"]),
                                    start_line=int(piece["start_line"]),
                                    end_line=int(piece["end_line"]),
                                    content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                                    symbol_names=", ".join(str(name) for name in piece.get("symbol_names", []))[:1000],
                                    token_count=len(text.split()),
                                    chunk_text=text,
                                )
                            )
                        db.add_all(rows)
                        chunk_count += len(rows)

                    processed += 1
                    job.processed_files = processed
                    job.skipped_files = skipped_files
                    job.chunk_count = chunk_count
                    job.progress_message = f"Indexed {path} ({processed}/{len(bounded_candidates)} files)."
                    if processed % PROGRESS_COMMIT_EVERY_FILES == 0:
                        db.commit()

                # A completed snapshot is switched atomically at the DB level:
                # consumers can keep reading the previous commit until this commit.
                db.execute(
                    delete(RepositoryChunk).where(
                        RepositoryChunk.repository_id == repository.id,
                        RepositoryChunk.user_id == repository.user_id,
                        RepositoryChunk.commit_sha != commit_sha,
                    )
                )
                repository.indexed_commit_sha = commit_sha
                repository.indexing_status = "indexed"
                repository.last_indexed_at = _now()
                repository.embedding_status = "pending"
                repository.embedding_provider = None
                repository.embedding_model = None
                repository.embedding_dimensions = None
                repository.last_embedded_at = None
                job.status = "completed"
                job.processed_files = processed
                job.skipped_files = skipped_files
                job.chunk_count = chunk_count
                job.error_message = None
                job.progress_message = (
                    f"Indexing completed with safety limits ({skipped_files} file(s) skipped)."
                    if skipped_files
                    else "Indexing completed successfully."
                )
                job.finished_at = _now()
                db.commit()

        except GitHubClientError as exc:
            _fail_job(
                db,
                normalized_job_id,
                prior_commit_sha=prior_commit_sha,
                prior_status=prior_status,
                safe_message=exc.detail,
            )
        except (IndexingPipelineError, ValueError) as exc:
            _fail_job(
                db,
                normalized_job_id,
                prior_commit_sha=prior_commit_sha,
                prior_status=prior_status,
                safe_message=str(exc),
            )
        except Exception:
            logger.exception("RepoLens indexing job failed (job_id=%s)", normalized_job_id)
            _fail_job(
                db,
                normalized_job_id,
                prior_commit_sha=prior_commit_sha,
                prior_status=prior_status,
                safe_message="Indexing failed due to an internal error. Check backend logs.",
            )



async def run_embedding_job(
    job_id: uuid.UUID | str,
    *,
    session_factory: Callable[[], Session] | None = None,
    embedding_provider_factory: Callable[[], Any] | None = None,
) -> None:
    """Generate and persist a selected provider/model's embeddings for an indexed snapshot.

    Embeddings are versioned by provider/model/dimension, so a failed model migration
    does not overwrite a previously completed embedding configuration.
    """
    from app.services.embeddings import (
        EmbeddingConfigurationError,
        EmbeddingProviderError,
        OpenAICompatibleEmbeddingProvider,
        get_embedding_configuration,
    )
    from app.models.repository_chunk_embedding import RepositoryChunkEmbedding

    try:
        normalized_job_id = job_id if isinstance(job_id, uuid.UUID) else uuid.UUID(str(job_id))
    except (ValueError, TypeError, AttributeError):
        return

    factory = session_factory or sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        job = db.get(IndexingJob, normalized_job_id)
        if job is None or job.status != "queued" or job.job_type != "embedding":
            return

        repository = db.scalar(
            select(Repository).where(
                Repository.id == job.repository_id,
                Repository.user_id == job.user_id,
            )
        )
        if repository is None:
            job.status = "failed"
            job.error_message = "The saved repository was not found."
            job.progress_message = "Embedding generation failed."
            job.finished_at = _now()
            db.commit()
            return

        previous_embedding_status = repository.embedding_status
        previous_provider = repository.embedding_provider
        previous_model = repository.embedding_model
        previous_dimensions = repository.embedding_dimensions

        try:
            settings = get_embedding_configuration()
            provider_name = settings.embeddings_provider.strip().lower()
            model_name = settings.embeddings_model.strip()
            dimensions = settings.embeddings_dimensions
            if (
                (job.embedding_provider is not None and job.embedding_provider != provider_name)
                or (job.embedding_model is not None and job.embedding_model != model_name)
                or (job.embedding_dimensions is not None and job.embedding_dimensions != dimensions)
            ):
                raise EmbeddingConfigurationError(
                    "The embedding configuration changed after this job was queued. "
                    "Start a new embedding job to use the current configuration."
                )
            provider_factory = embedding_provider_factory or (
                lambda: OpenAICompatibleEmbeddingProvider(settings)
            )
            commit_sha = repository.indexed_commit_sha
            if repository.indexing_status != "indexed" or not commit_sha:
                raise IndexingPipelineError(
                    "Index source files successfully before generating embeddings."
                )

            chunks = db.scalars(
                select(RepositoryChunk)
                .where(
                    RepositoryChunk.repository_id == repository.id,
                    RepositoryChunk.user_id == repository.user_id,
                    RepositoryChunk.commit_sha == commit_sha,
                )
                .order_by(RepositoryChunk.file_path, RepositoryChunk.chunk_index)
            ).all()
            if not chunks:
                raise IndexingPipelineError(
                    "No source chunks are available. Index the repository before generating embeddings."
                )

            job.status = "running"
            job.attempt_count += 1
            job.started_at = _now()
            job.finished_at = None
            job.error_message = None
            job.commit_sha = commit_sha
            job.embedding_provider = provider_name
            job.embedding_model = model_name
            job.embedding_dimensions = dimensions
            job.total_files = len(chunks)
            job.processed_files = 0
            job.skipped_files = 0
            job.chunk_count = len(chunks)
            job.progress_message = (
                f"Preparing {len(chunks)} source chunks for {model_name} embeddings."
            )
            repository.embedding_status = "embedding"
            db.commit()

            existing_embeddings = db.scalars(
                select(RepositoryChunkEmbedding).where(
                    RepositoryChunkEmbedding.repository_id == repository.id,
                    RepositoryChunkEmbedding.user_id == repository.user_id,
                    RepositoryChunkEmbedding.commit_sha == commit_sha,
                    RepositoryChunkEmbedding.provider == provider_name,
                    RepositoryChunkEmbedding.model == model_name,
                    RepositoryChunkEmbedding.dimensions == dimensions,
                )
            ).all()
            by_chunk_id = {item.chunk_id: item for item in existing_embeddings}
            pending_chunks = [
                chunk for chunk in chunks
                if (
                    chunk.id not in by_chunk_id
                    or by_chunk_id[chunk.id].content_hash != chunk.content_hash
                )
            ]
            already_complete = len(chunks) - len(pending_chunks)
            job.processed_files = already_complete
            job.progress_message = (
                f"{already_complete} of {len(chunks)} chunks already have matching embeddings."
            )
            db.commit()

            if not pending_chunks:
                job.status = "completed"
                job.progress_message = "Embeddings for this source commit and model are already up to date."
                job.finished_at = _now()
                repository.embedding_status = "embedded"
                repository.embedding_provider = provider_name
                repository.embedding_model = model_name
                repository.embedding_dimensions = dimensions
                if repository.last_embedded_at is None:
                    repository.last_embedded_at = _now()
                db.commit()
                return

            batch_size = settings.embeddings_batch_size
            async with provider_factory() as provider:
                if (
                    provider.provider_name != provider_name
                    or provider.model_name != model_name
                    or provider.dimensions != dimensions
                ):
                    raise EmbeddingProviderError(
                        "The embedding provider does not match the configured provider, model, and dimensions."
                    )

                for batch_start in range(0, len(pending_chunks), batch_size):
                    batch = pending_chunks[batch_start: batch_start + batch_size]
                    vectors = await provider.embed_texts([chunk.chunk_text for chunk in batch])
                    if len(vectors) != len(batch):
                        raise EmbeddingProviderError(
                            "The embedding provider returned an incomplete batch."
                        )

                    for chunk, vector in zip(batch, vectors, strict=True):
                        if len(vector) != dimensions or any(
                            isinstance(value, bool)
                            or not isinstance(value, (int, float))
                            or not math.isfinite(float(value))
                            for value in vector
                        ):
                            raise EmbeddingProviderError(
                                "The embedding provider returned an invalid vector."
                            )
                        embedding = by_chunk_id.get(chunk.id)
                        if embedding is None:
                            embedding = RepositoryChunkEmbedding(
                                chunk_id=chunk.id,
                                repository_id=repository.id,
                                user_id=repository.user_id,
                                commit_sha=commit_sha,
                                provider=provider_name,
                                model=model_name,
                                dimensions=dimensions,
                                content_hash=chunk.content_hash,
                                vector=[float(value) for value in vector],
                            )
                            db.add(embedding)
                            by_chunk_id[chunk.id] = embedding
                        else:
                            embedding.content_hash = chunk.content_hash
                            embedding.vector = [float(value) for value in vector]
                    processed_count = already_complete + batch_start + len(batch)
                    job.processed_files = processed_count
                    job.progress_message = (
                        f"Generated embeddings for {processed_count}/{len(chunks)} source chunks."
                    )
                    db.commit()

            repository.embedding_status = "embedded"
            repository.embedding_provider = provider_name
            repository.embedding_model = model_name
            repository.embedding_dimensions = dimensions
            repository.last_embedded_at = _now()
            job.status = "completed"
            job.processed_files = len(chunks)
            job.chunk_count = len(chunks)
            job.skipped_files = 0
            job.error_message = None
            job.progress_message = (
                f"Generated {len(chunks)} embeddings with {provider_name}/{model_name}."
            )
            job.finished_at = _now()
            db.commit()

        except (EmbeddingConfigurationError, EmbeddingProviderError, IndexingPipelineError, ValueError) as exc:
            db.rollback()
            failed_job = db.get(IndexingJob, normalized_job_id)
            failed_repository = db.scalar(
                select(Repository).where(
                    Repository.id == failed_job.repository_id,
                    Repository.user_id == failed_job.user_id,
                )
            ) if failed_job is not None else None
            if failed_job is not None:
                failed_job.status = "failed"
                failed_job.error_message = str(exc)[:1000]
                failed_job.progress_message = "Embedding generation failed. Existing completed embeddings were preserved."
                failed_job.finished_at = _now()
            if failed_repository is not None:
                if previous_embedding_status == "embedded":
                    failed_repository.embedding_status = "embedded"
                    failed_repository.embedding_provider = previous_provider
                    failed_repository.embedding_model = previous_model
                    failed_repository.embedding_dimensions = previous_dimensions
                else:
                    failed_repository.embedding_status = "failed"
            db.commit()
        except Exception:
            logger.exception("RepoLens embedding job failed (job_id=%s)", normalized_job_id)
            db.rollback()
            failed_job = db.get(IndexingJob, normalized_job_id)
            failed_repository = db.scalar(
                select(Repository).where(
                    Repository.id == failed_job.repository_id,
                    Repository.user_id == failed_job.user_id,
                )
            ) if failed_job is not None else None
            if failed_job is not None:
                failed_job.status = "failed"
                failed_job.error_message = "Embedding generation failed due to an internal error. Check backend logs."
                failed_job.progress_message = "Embedding generation failed."
                failed_job.finished_at = _now()
            if failed_repository is not None:
                if previous_embedding_status == "embedded":
                    failed_repository.embedding_status = "embedded"
                    failed_repository.embedding_provider = previous_provider
                    failed_repository.embedding_model = previous_model
                    failed_repository.embedding_dimensions = previous_dimensions
                else:
                    failed_repository.embedding_status = "failed"
            db.commit()
