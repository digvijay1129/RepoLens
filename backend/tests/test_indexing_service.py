import base64
from uuid import UUID

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.indexing_job import IndexingJob
from app.models.repository import Repository
from app.models.repository_chunk import RepositoryChunk
from app.models.repository_chunk_embedding import RepositoryChunkEmbedding
from app.models.user import User
from app.services.github_client import GitHubClientError
from app.services.indexing import run_embedding_job, run_indexing_job

COMMIT_SHA = "a" * 40
OLD_COMMIT_SHA = "c" * 40


class FakeGitHubClient:
    def __init__(self, *, fail_tree: bool = False):
        self.fail_tree = fail_tree
        self.tree_calls = 0
        self.blob_calls = 0
        self.source = "def greet(name):\n    return f'hello {name}'\n"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def list_branches(self, owner: str, repository: str):
        return [{"name": "main", "commit_sha": COMMIT_SHA, "protected": True}]

    async def _get_json(self, path: str, params=None):
        if "/git/trees/" in path:
            self.tree_calls += 1
            if self.fail_tree:
                raise GitHubClientError(429, "GitHub API rate limit reached. Please retry later.")
            return {
                "truncated": False,
                "tree": [
                    {"path": "src/main.py", "type": "blob", "sha": "b" * 40, "size": len(self.source.encode())},
                    {"path": ".env.example", "type": "blob", "sha": "d" * 40, "size": 20},
                    {"path": "package-lock.json", "type": "blob", "sha": "e" * 40, "size": 30},
                    {"path": "assets/logo.png", "type": "blob", "sha": "f" * 40, "size": 500},
                    {"path": "node_modules/tool/index.js", "type": "blob", "sha": "9" * 40, "size": 40},
                ],
            }
        if "/git/blobs/" in path:
            self.blob_calls += 1
            raw = self.source.encode("utf-8")
            return {
                "size": len(raw),
                "encoding": "base64",
                "content": base64.b64encode(raw).decode("ascii"),
            }
        raise AssertionError(f"Unexpected GitHub path: {path}")


@pytest.fixture()
def indexing_context():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = lambda: Session(engine, expire_on_commit=False)

    with factory() as db:
        user = User(
            email="indexer@example.com",
            password_hash="not-used-in-this-test",
            display_name="Indexer",
            is_active=True,
        )
        db.add(user)
        db.flush()
        repository = Repository(
            user_id=user.id,
            github_repository_id=123,
            github_owner="owner",
            github_name="repo",
            full_name="owner/repo",
            canonical_url="https://github.com/owner/repo",
            default_branch="main",
            selected_branch="main",
            indexing_status="pending",
        )
        db.add(repository)
        db.flush()
        job = IndexingJob(
            repository_id=repository.id,
            user_id=user.id,
            status="queued",
            progress_message="Queued for indexing.",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        db.refresh(repository)
        ids = {"user_id": user.id, "repository_id": repository.id, "job_id": job.id}

    yield factory, engine, ids
    engine.dispose()


@pytest.mark.asyncio
async def test_worker_persists_chunks_and_marks_index_snapshot_complete(indexing_context) -> None:
    factory, _engine, ids = indexing_context
    fake_github = FakeGitHubClient()

    await run_indexing_job(
        ids["job_id"],
        session_factory=factory,
        github_client_factory=lambda: fake_github,
    )

    with factory() as db:
        job = db.get(IndexingJob, ids["job_id"])
        repository = db.get(Repository, ids["repository_id"])
        chunks = db.scalars(
            select(RepositoryChunk).where(
                RepositoryChunk.repository_id == ids["repository_id"]
            )
        ).all()

    assert job.status == "completed"
    assert job.attempt_count == 1
    assert job.total_files == 1
    assert job.processed_files == 1
    assert job.skipped_files >= 4
    assert job.chunk_count == len(chunks) >= 1
    assert job.commit_sha == COMMIT_SHA
    assert repository.indexing_status == "indexed"
    assert repository.indexed_commit_sha == COMMIT_SHA
    assert repository.last_indexed_at is not None
    assert [(chunk.file_path, chunk.language) for chunk in chunks] == [("src/main.py", "python")]
    assert chunks[0].start_line == 1
    assert "def greet" in chunks[0].chunk_text
    assert "greet" in chunks[0].symbol_names
    assert len(chunks[0].content_hash) == 64
    assert ".env.example" not in chunks[0].chunk_text


@pytest.mark.asyncio
async def test_worker_is_idempotent_for_the_same_completed_commit(indexing_context) -> None:
    factory, _engine, ids = indexing_context
    fake_github = FakeGitHubClient()
    await run_indexing_job(
        ids["job_id"],
        session_factory=factory,
        github_client_factory=lambda: fake_github,
    )
    first_blob_calls = fake_github.blob_calls

    with factory() as db:
        second_job = IndexingJob(
            repository_id=ids["repository_id"],
            user_id=ids["user_id"],
            status="queued",
            progress_message="Queued for indexing.",
        )
        db.add(second_job)
        db.commit()
        db.refresh(second_job)
        second_job_id = second_job.id

    await run_indexing_job(
        second_job_id,
        session_factory=factory,
        github_client_factory=lambda: fake_github,
    )

    with factory() as db:
        second_job = db.get(IndexingJob, second_job_id)
        count = db.scalar(
            select(__import__("sqlalchemy").func.count())
            .select_from(RepositoryChunk)
            .where(RepositoryChunk.repository_id == ids["repository_id"])
        )

    assert second_job.status == "completed"
    assert "already indexed" in second_job.progress_message
    assert fake_github.blob_calls == first_blob_calls
    assert count == 1


@pytest.mark.asyncio
async def test_failed_reindex_preserves_the_previous_completed_snapshot(indexing_context) -> None:
    factory, _engine, ids = indexing_context
    with factory() as db:
        repository = db.get(Repository, ids["repository_id"])
        repository.indexed_commit_sha = OLD_COMMIT_SHA
        repository.indexing_status = "indexed"
        db.add(
            RepositoryChunk(
                repository_id=repository.id,
                user_id=repository.user_id,
                commit_sha=OLD_COMMIT_SHA,
                file_path="README.md",
                language="markdown",
                chunk_index=0,
                start_line=1,
                end_line=1,
                content_hash="d" * 64,
                token_count=3,
                chunk_text="# previous successful snapshot",
            )
        )
        db.commit()

    fake_github = FakeGitHubClient(fail_tree=True)
    await run_indexing_job(
        ids["job_id"],
        session_factory=factory,
        github_client_factory=lambda: fake_github,
    )

    with factory() as db:
        job = db.get(IndexingJob, ids["job_id"])
        repository = db.get(Repository, ids["repository_id"])
        chunks = db.scalars(
            select(RepositoryChunk).where(
                RepositoryChunk.repository_id == ids["repository_id"]
            )
        ).all()

    assert job.status == "failed"
    assert job.error_message == "GitHub API rate limit reached. Please retry later."
    assert repository.indexing_status == "indexed"
    assert repository.indexed_commit_sha == OLD_COMMIT_SHA
    assert len(chunks) == 1
    assert chunks[0].commit_sha == OLD_COMMIT_SHA



class FakeEmbeddingProvider:
    provider_name = "openai_compatible"
    model_name = "test-embedding-model"
    dimensions = 3

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.fail:
            from app.services.embeddings import EmbeddingProviderError
            raise EmbeddingProviderError("The embedding provider rate limit was reached. Retry later.")
        return [[float(index + 1), 0.25, -0.5] for index, _ in enumerate(texts)]


def create_ready_embedding_job(factory, ids, *, provider="openai_compatible", model="test-embedding-model", dimensions=3):
    with factory() as db:
        repository = db.get(Repository, ids["repository_id"])
        repository.indexed_commit_sha = COMMIT_SHA
        repository.indexing_status = "indexed"
        chunk = RepositoryChunk(
            repository_id=repository.id,
            user_id=repository.user_id,
            commit_sha=COMMIT_SHA,
            file_path="src/main.py",
            language="python",
            chunk_index=0,
            start_line=1,
            end_line=2,
            content_hash="a" * 64,
            symbol_names="greet",
            token_count=7,
            chunk_text="def greet(name): return name",
        )
        db.add(chunk)
        job = IndexingJob(
            repository_id=repository.id,
            user_id=repository.user_id,
            job_type="embedding",
            embedding_provider=provider,
            embedding_model=model,
            embedding_dimensions=dimensions,
            status="queued",
            commit_sha=COMMIT_SHA,
            progress_message="Queued embeddings.",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        ids["embedding_job_id"] = job.id
        ids["chunk_id"] = chunk.id
    return ids


@pytest.mark.asyncio
async def test_embedding_worker_persists_vector_metadata_and_is_idempotent(indexing_context, monkeypatch) -> None:
    from pydantic import SecretStr
    from app.core.config import Settings
    from app.services import embeddings as embedding_service

    factory, _engine, ids = indexing_context
    create_ready_embedding_job(factory, ids)
    settings = Settings(
        environment="test",
        embeddings_enabled=True,
        embeddings_provider="openai_compatible",
        embeddings_api_key=SecretStr("test-key"),
        embeddings_base_url="https://embedding.example.test/v1",
        embeddings_model="test-embedding-model",
        embeddings_dimensions=3,
        embeddings_batch_size=2,
    )
    monkeypatch.setattr(embedding_service, "get_embedding_configuration", lambda: settings)
    fake_provider = FakeEmbeddingProvider()

    await run_embedding_job(
        ids["embedding_job_id"],
        session_factory=factory,
        embedding_provider_factory=lambda: fake_provider,
    )

    with factory() as db:
        job = db.get(IndexingJob, ids["embedding_job_id"])
        repository = db.get(Repository, ids["repository_id"])
        vector_rows = db.scalars(
            select(RepositoryChunkEmbedding).where(
                RepositoryChunkEmbedding.repository_id == ids["repository_id"]
            )
        ).all()
    assert job.status == "completed"
    assert job.job_type == "embedding"
    assert job.processed_files == 1
    assert job.embedding_model == "test-embedding-model"
    assert repository.embedding_status == "embedded"
    assert repository.embedding_provider == "openai_compatible"
    assert repository.embedding_model == "test-embedding-model"
    assert repository.embedding_dimensions == 3
    assert repository.last_embedded_at is not None
    assert len(vector_rows) == 1
    assert vector_rows[0].vector == [1.0, 0.25, -0.5]
    assert vector_rows[0].dimensions == 3
    assert vector_rows[0].content_hash == "a" * 64

    second_job_id = create_ready_embedding_job_and_get_second(factory, ids)
    second_provider = FakeEmbeddingProvider()
    await run_embedding_job(
        second_job_id,
        session_factory=factory,
        embedding_provider_factory=lambda: second_provider,
    )
    with factory() as db:
        second_job = db.get(IndexingJob, second_job_id)
        count = db.scalar(
            select(__import__("sqlalchemy").func.count())
            .select_from(RepositoryChunkEmbedding)
            .where(RepositoryChunkEmbedding.repository_id == ids["repository_id"])
        )
    assert second_job.status == "completed"
    assert "already up to date" in second_job.progress_message
    assert second_provider.calls == []
    assert count == 1


def create_ready_embedding_job_and_get_second(factory, ids):
    with factory() as db:
        job = IndexingJob(
            repository_id=ids["repository_id"],
            user_id=ids["user_id"],
            job_type="embedding",
            status="queued",
            progress_message="Queued retry.",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job.id


@pytest.mark.asyncio
async def test_failed_embedding_attempt_preserves_the_active_embedding_configuration(indexing_context, monkeypatch) -> None:
    from pydantic import SecretStr
    from app.core.config import Settings
    from app.services import embeddings as embedding_service

    factory, _engine, ids = indexing_context
    create_ready_embedding_job(factory, ids)
    settings = Settings(
        environment="test",
        embeddings_enabled=True,
        embeddings_provider="openai_compatible",
        embeddings_api_key=SecretStr("test-key"),
        embeddings_base_url="https://embedding.example.test/v1",
        embeddings_model="test-embedding-model",
        embeddings_dimensions=3,
        embeddings_batch_size=2,
    )
    monkeypatch.setattr(embedding_service, "get_embedding_configuration", lambda: settings)
    with factory() as db:
        repository = db.get(Repository, ids["repository_id"])
        repository.embedding_status = "embedded"
        repository.embedding_provider = "openai_compatible"
        repository.embedding_model = "previous-model"
        repository.embedding_dimensions = 3
        db.add(RepositoryChunkEmbedding(
            chunk_id=ids["chunk_id"],
            repository_id=repository.id,
            user_id=repository.user_id,
            commit_sha=COMMIT_SHA,
            provider="openai_compatible",
            model="previous-model",
            dimensions=3,
            content_hash="a" * 64,
            vector=[0.1, 0.2, 0.3],
        ))
        db.commit()

    failing_provider = FakeEmbeddingProvider(fail=True)
    await run_embedding_job(
        ids["embedding_job_id"],
        session_factory=factory,
        embedding_provider_factory=lambda: failing_provider,
    )

    with factory() as db:
        job = db.get(IndexingJob, ids["embedding_job_id"])
        repository = db.get(Repository, ids["repository_id"])
        old_rows = db.scalars(
            select(RepositoryChunkEmbedding).where(
                RepositoryChunkEmbedding.repository_id == ids["repository_id"],
                RepositoryChunkEmbedding.model == "previous-model",
            )
        ).all()

    assert job.status == "failed"
    assert "rate limit" in job.error_message.lower()
    assert repository.embedding_status == "embedded"
    assert repository.embedding_model == "previous-model"
    assert len(old_rows) == 1
    assert old_rows[0].vector == [0.1, 0.2, 0.3]
