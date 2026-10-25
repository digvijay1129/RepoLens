"""Unit tests for owner-scoped semantic, lexical and hybrid retrieval."""

import uuid

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.models.repository import Repository
from app.models.repository_chunk import RepositoryChunk
from app.models.repository_chunk_embedding import RepositoryChunkEmbedding
from app.models.user import User
from app.services import retrieval
from app.services.retrieval import SearchReadinessError, search_repository_chunks

COMMIT = "a" * 40


class FakeQueryEmbeddingProvider:
    provider_name = "openai_compatible"
    model_name = "test-model"
    dimensions = 3

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        assert len(texts) == 1
        assert texts[0].strip()
        return [[1.0, 0.0, 0.0]]


@pytest.fixture()
def retrieval_db():
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
    with Session(engine, expire_on_commit=False) as db:
        owner = User(email="retrieval-owner@example.com", password_hash="test-hash")
        other = User(email="retrieval-other@example.com", password_hash="test-hash")
        db.add_all([owner, other])
        db.flush()
        repository = Repository(
            user_id=owner.id,
            github_owner="ExampleOrg",
            github_name="DemoRepo",
            full_name="exampleorg/demorepo",
            canonical_url="https://github.com/ExampleOrg/DemoRepo",
            indexing_status="indexed",
            indexed_commit_sha=COMMIT,
            selected_branch="main",
            embedding_status="embedded",
            embedding_provider="openai_compatible",
            embedding_model="test-model",
            embedding_dimensions=3,
        )
        other_repository = Repository(
            user_id=other.id,
            github_owner="ExampleOrg",
            github_name="PrivateForOther",
            full_name="exampleorg/privateforother",
            canonical_url="https://github.com/ExampleOrg/PrivateForOther",
            indexing_status="indexed",
            indexed_commit_sha=COMMIT,
        )
        db.add_all([repository, other_repository])
        db.flush()

        chunk1 = RepositoryChunk(
            repository_id=repository.id,
            user_id=owner.id,
            commit_sha=COMMIT,
            file_path="backend/app/auth.py",
            language="python",
            chunk_index=0,
            start_line=10,
            end_line=22,
            content_hash="1" * 64,
            symbol_names="authenticate_user, get_current_user",
            token_count=15,
            chunk_text="def authenticate_user(token):\n    return get_current_user(token)",
        )
        chunk2 = RepositoryChunk(
            repository_id=repository.id,
            user_id=owner.id,
            commit_sha=COMMIT,
            file_path="backend/app/database.py",
            language="python",
            chunk_index=0,
            start_line=3,
            end_line=18,
            content_hash="2" * 64,
            symbol_names="create_database",
            token_count=18,
            chunk_text="def create_database(url):\n    connect to PostgreSQL using SQLAlchemy",
        )
        other_chunk = RepositoryChunk(
            repository_id=other_repository.id,
            user_id=other.id,
            commit_sha=COMMIT,
            file_path="private.py",
            language="python",
            chunk_index=0,
            start_line=1,
            end_line=2,
            content_hash="3" * 64,
            symbol_names="secret_function",
            token_count=3,
            chunk_text="def authenticate_user_secret(): pass",
        )
        db.add_all([chunk1, chunk2, other_chunk])
        db.flush()
        db.add_all([
            RepositoryChunkEmbedding(
                chunk_id=chunk1.id,
                repository_id=repository.id,
                user_id=owner.id,
                commit_sha=COMMIT,
                provider="openai_compatible",
                model="test-model",
                dimensions=3,
                content_hash=chunk1.content_hash,
                vector=[1.0, 0.0, 0.0],
            ),
            RepositoryChunkEmbedding(
                chunk_id=chunk2.id,
                repository_id=repository.id,
                user_id=owner.id,
                commit_sha=COMMIT,
                provider="openai_compatible",
                model="test-model",
                dimensions=3,
                content_hash=chunk2.content_hash,
                vector=[0.0, 1.0, 0.0],
            ),
            RepositoryChunkEmbedding(
                chunk_id=other_chunk.id,
                repository_id=other_repository.id,
                user_id=other.id,
                commit_sha=COMMIT,
                provider="openai_compatible",
                model="test-model",
                dimensions=3,
                content_hash=other_chunk.content_hash,
                vector=[1.0, 0.0, 0.0],
            ),
        ])
        db.commit()
        ids = {
            "owner_id": owner.id,
            "other_id": other.id,
            "repository": repository,
            "other_repository": other_repository,
            "chunk1": chunk1.id,
        }
        yield db, ids
    engine.dispose()


@pytest.mark.asyncio
async def test_keyword_search_returns_line_citation_and_only_owned_current_source(retrieval_db) -> None:
    db, ids = retrieval_db
    result = await search_repository_chunks(
        db, ids["repository"], ids["owner_id"], "authenticate_user", mode="keyword", limit=5
    )

    assert result["repository"] == "exampleorg/demorepo"
    assert result["commit_sha"] == COMMIT
    assert result["result_count"] == 1
    item = result["results"][0]
    assert item["file_path"] == "backend/app/auth.py"
    assert item["start_line"] == 10
    assert item["end_line"] == 22
    assert item["symbol_names"] == ["authenticate_user", "get_current_user"]
    assert item["match_types"] == ["keyword"]
    assert item["citation_url"] == (
        f"https://github.com/ExampleOrg/DemoRepo/blob/{COMMIT}/backend/app/auth.py#L10-L22"
    )
    assert "private.py" not in str(result)


@pytest.mark.asyncio
async def test_semantic_search_uses_configured_provider_and_current_embedding_model(retrieval_db, monkeypatch) -> None:
    db, ids = retrieval_db
    settings = Settings(
        environment="test",
        embeddings_enabled=True,
        embeddings_provider="openai_compatible",
        embeddings_api_key=SecretStr("test-key"),
        embeddings_base_url="https://embedding.example.test/v1",
        embeddings_model="test-model",
        embeddings_dimensions=3,
        embeddings_batch_size=4,
    )
    monkeypatch.setattr(retrieval, "get_embedding_configuration", lambda: settings)

    result = await search_repository_chunks(
        db,
        ids["repository"],
        ids["owner_id"],
        "authentication flow",
        mode="semantic",
        limit=5,
        embedding_provider_factory=lambda _: FakeQueryEmbeddingProvider(),
    )

    assert result["result_count"] == 2
    assert result["results"][0]["file_path"] == "backend/app/auth.py"
    assert result["results"][0]["score"] == 1.0
    assert result["results"][0]["match_types"] == ["semantic"]


@pytest.mark.asyncio
async def test_hybrid_search_fuses_semantic_and_keyword_rankings(retrieval_db, monkeypatch) -> None:
    db, ids = retrieval_db
    settings = Settings(
        environment="test",
        embeddings_enabled=True,
        embeddings_provider="openai_compatible",
        embeddings_api_key=SecretStr("test-key"),
        embeddings_base_url="https://embedding.example.test/v1",
        embeddings_model="test-model",
        embeddings_dimensions=3,
        embeddings_batch_size=4,
    )
    monkeypatch.setattr(retrieval, "get_embedding_configuration", lambda: settings)

    result = await search_repository_chunks(
        db,
        ids["repository"],
        ids["owner_id"],
        "authenticate_user PostgreSQL",
        mode="hybrid",
        limit=5,
        embedding_provider_factory=lambda _: FakeQueryEmbeddingProvider(),
    )

    assert result["result_count"] == 2
    assert all(item["score"] <= 1.0 for item in result["results"])
    assert any(item["match_types"] == ["semantic", "keyword"] for item in result["results"])
    assert all("private.py" != item["file_path"] for item in result["results"])


@pytest.mark.asyncio
async def test_search_rejects_other_owner_and_unindexed_repository(retrieval_db) -> None:
    db, ids = retrieval_db
    with pytest.raises(SearchReadinessError, match="not found"):
        await search_repository_chunks(
            db, ids["repository"], ids["other_id"], "auth", mode="keyword"
        )

    repository = ids["repository"]
    repository.indexing_status = "pending"
    repository.indexed_commit_sha = None
    with pytest.raises(SearchReadinessError, match="Index source files"):
        await search_repository_chunks(db, repository, ids["owner_id"], "auth", mode="keyword")


@pytest.mark.asyncio
async def test_semantic_search_rejects_embedding_model_mismatch(retrieval_db, monkeypatch) -> None:
    db, ids = retrieval_db
    settings = Settings(
        environment="test",
        embeddings_enabled=True,
        embeddings_provider="openai_compatible",
        embeddings_api_key=SecretStr("test-key"),
        embeddings_base_url="https://embedding.example.test/v1",
        embeddings_model="different-model",
        embeddings_dimensions=3,
        embeddings_batch_size=4,
    )
    monkeypatch.setattr(retrieval, "get_embedding_configuration", lambda: settings)
    with pytest.raises(SearchReadinessError, match="does not match"):
        await search_repository_chunks(
            db,
            ids["repository"],
            ids["owner_id"],
            "authenticate user",
            mode="semantic",
            embedding_provider_factory=lambda _: FakeQueryEmbeddingProvider(),
        )
