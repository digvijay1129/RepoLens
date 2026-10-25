"""Authentication and persisted repository ownership tests."""

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.api.routes import repositories as repository_routes
from app.models.indexing_job import IndexingJob
from app.models.repository import Repository
from app.models.repository_chunk import RepositoryChunk
from app.models.repository_chunk_embedding import RepositoryChunkEmbedding
from app.models.user import User
from app.services import auth as auth_service
from app.services.github_client import get_github_client


class FakeGitHubClient:
    async def inspect_repository(self, repository_url: str) -> dict:
        return {
            "id": 741852,
            "name": "RepoLens",
            "full_name": "Digvijay1129/RepoLens",
            "description": "Repository intelligence",
            "html_url": "https://github.com/Digvijay1129/RepoLens",
            "default_branch": "main",
            "language": "Python",
            "stargazers_count": 4,
            "forks_count": 2,
            "open_issues_count": 3,
            "size": 170,
            "updated_at": datetime(2026, 10, 25, tzinfo=timezone.utc).isoformat(),
            "license_name": "MIT License",
            "archived": False,
            "private": False,
        }

    async def list_branches(self, owner: str, repository: str, max_pages: int = 5) -> list[dict]:
        return [
            {"name": "main", "commit_sha": "a" * 40, "protected": True},
            {"name": "feature/add-tests", "commit_sha": "b" * 40, "protected": False},
        ]

    async def list_directory(self, owner: str, repository: str, path=None, ref=None) -> dict:
        return {
            "full_name": f"{owner}/{repository}",
            "owner": owner,
            "repository": repository,
            "path": path or "",
            "ref": ref,
            "items": [],
            "may_be_truncated": False,
            "notice": None,
        }


@pytest.fixture()
def api_client(monkeypatch):
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

    def override_db_session():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_github_client] = lambda: FakeGitHubClient()
    monkeypatch.setattr(
        auth_service,
        "get_settings",
        lambda: Settings(
            jwt_secret_key=SecretStr("repolens-test-signing-secret-32-bytes-minimum"),
            jwt_access_token_expire_minutes=60,
        ),
    )

    with TestClient(app) as client:
        app.state.test_engine = engine
        yield client

    app.dependency_overrides.clear()
    engine.dispose()


def create_account(client: TestClient, email: str = "dev@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "a-strong-test-password-2026",
            "display_name": "Developer",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_hashes_password_and_authenticated_me_returns_profile(api_client: TestClient) -> None:
    created = create_account(api_client, "Developer@Example.com")
    assert created["user"]["email"] == "developer@example.com"
    assert created["token_type"] == "bearer"
    assert created["access_token"]

    response = api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {created['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "developer@example.com"
    assert "password_hash" not in response.json()


def test_login_returns_generic_error_for_wrong_password(api_client: TestClient) -> None:
    create_account(api_client)

    response = api_client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "this-is-the-wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_duplicate_registration_is_rejected(api_client: TestClient) -> None:
    create_account(api_client)
    response = api_client.post(
        "/api/v1/auth/register",
        json={"email": "DEV@example.com", "password": "another-strong-password-2026"},
    )
    assert response.status_code == 409


def test_saved_repository_is_persistent_and_branch_selection_is_verified(
    api_client: TestClient,
) -> None:
    account = create_account(api_client)
    headers = {"Authorization": f"Bearer {account['access_token']}"}

    saved_response = api_client.post(
        "/api/v1/repositories/saved",
        headers=headers,
        json={"repository_url": "https://github.com/Digvijay1129/RepoLens"},
    )
    assert saved_response.status_code == 201, saved_response.text
    saved = saved_response.json()
    assert saved["full_name"] == "Digvijay1129/RepoLens"
    assert saved["selected_branch"] == "main"

    listed = api_client.get("/api/v1/repositories/saved", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == saved["id"]

    branches = api_client.get(
        f"/api/v1/repositories/saved/{saved['id']}/branches",
        headers=headers,
    )
    assert branches.status_code == 200
    assert {branch["name"] for branch in branches.json()["items"]} == {
        "main", "feature/add-tests"
    }

    invalid = api_client.patch(
        f"/api/v1/repositories/saved/{saved['id']}/branch",
        headers=headers,
        json={"selected_branch": "feature/does-not-exist"},
    )
    assert invalid.status_code == 422

    selected = api_client.patch(
        f"/api/v1/repositories/saved/{saved['id']}/branch",
        headers=headers,
        json={"selected_branch": "feature/add-tests"},
    )
    assert selected.status_code == 200
    assert selected.json()["selected_branch"] == "feature/add-tests"

    listed_after = api_client.get("/api/v1/repositories/saved", headers=headers)
    assert listed_after.json()[0]["selected_branch"] == "feature/add-tests"


def test_users_cannot_list_or_delete_another_users_repository(api_client: TestClient) -> None:
    first_user = create_account(api_client, "first@example.com")
    first_headers = {"Authorization": f"Bearer {first_user['access_token']}"}
    saved = api_client.post(
        "/api/v1/repositories/saved",
        headers=first_headers,
        json={"repository_url": "https://github.com/Digvijay1129/RepoLens"},
    ).json()

    second_user = create_account(api_client, "second@example.com")
    second_headers = {"Authorization": f"Bearer {second_user['access_token']}"}

    assert api_client.get("/api/v1/repositories/saved", headers=second_headers).json() == []
    branch_response = api_client.get(
        f"/api/v1/repositories/saved/{saved['id']}/branches",
        headers=second_headers,
    )
    assert branch_response.status_code == 404

    branch_update = api_client.patch(
        f"/api/v1/repositories/saved/{saved['id']}/branch",
        headers=second_headers,
        json={"selected_branch": "feature/add-tests"},
    )
    assert branch_update.status_code == 404

    delete_response = api_client.delete(
        f"/api/v1/repositories/saved/{saved['id']}",
        headers=second_headers,
    )
    assert delete_response.status_code == 404

    still_owned = api_client.get("/api/v1/repositories/saved", headers=first_headers)
    assert len(still_owned.json()) == 1


def test_saved_repository_management_requires_authentication(api_client: TestClient) -> None:
    assert api_client.get("/api/v1/repositories/saved").status_code == 401
    assert api_client.post(
        "/api/v1/repositories/saved",
        json={"repository_url": "https://github.com/owner/repo"},
    ).status_code == 401


def test_user_cannot_use_expired_or_malformed_token(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert response.status_code == 401



def test_indexing_job_api_is_authenticated_idempotent_and_owner_scoped(
    api_client: TestClient,
    monkeypatch,
) -> None:
    async def no_op_worker(job_id) -> None:
        return None

    monkeypatch.setattr(repository_routes, "run_indexing_job", no_op_worker)
    first_user = create_account(api_client, "index-owner@example.com")
    first_headers = {"Authorization": f"Bearer {first_user['access_token']}"}
    saved_response = api_client.post(
        "/api/v1/repositories/saved",
        headers=first_headers,
        json={"repository_url": "https://github.com/Digvijay1129/RepoLens"},
    )
    assert saved_response.status_code == 201
    repository_id = saved_response.json()["id"]

    queued = api_client.post(
        f"/api/v1/repositories/saved/{repository_id}/index",
        headers=first_headers,
    )
    assert queued.status_code == 202
    job = queued.json()
    assert job["status"] == "queued"
    assert job["processed_files"] == 0
    assert job["chunk_count"] == 0

    same_job = api_client.post(
        f"/api/v1/repositories/saved/{repository_id}/index",
        headers=first_headers,
    )
    assert same_job.status_code == 202
    assert same_job.json()["id"] == job["id"]

    status_response = api_client.get(
        f"/api/v1/repositories/saved/{repository_id}/jobs/{job['id']}",
        headers=first_headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["progress_message"] == "Queued for indexing."

    second_user = create_account(api_client, "index-other@example.com")
    second_headers = {"Authorization": f"Bearer {second_user['access_token']}"}
    assert api_client.get(
        f"/api/v1/repositories/saved/{repository_id}/jobs/{job['id']}",
        headers=second_headers,
    ).status_code == 404

    assert api_client.post(
        f"/api/v1/repositories/saved/{repository_id}/index",
    ).status_code == 401



def test_embedding_generation_requires_explicit_provider_configuration(api_client: TestClient) -> None:
    account = create_account(api_client, "embeddings-config@example.com")
    headers = {"Authorization": f"Bearer {account['access_token']}"}
    saved_response = api_client.post(
        "/api/v1/repositories/saved",
        headers=headers,
        json={"repository_url": "https://github.com/Digvijay1129/RepoLens"},
    )
    assert saved_response.status_code == 201, saved_response.text
    repository_id = saved_response.json()["id"]

    response = api_client.post(
        f"/api/v1/repositories/saved/{repository_id}/embeddings",
        headers=headers,
    )
    assert response.status_code == 503
    assert "EMBEDDINGS_ENABLED=true" in response.json()["detail"]
    assert "API_KEY" not in response.json()["detail"]



def test_embedding_job_is_queued_idempotently_and_scoped_to_repository_owner(
    api_client: TestClient,
    monkeypatch,
) -> None:
    from app.core.config import Settings
    from pydantic import SecretStr

    settings = Settings(
        environment="test",
        embeddings_enabled=True,
        embeddings_provider="openai_compatible",
        embeddings_api_key=SecretStr("test-api-key"),
        embeddings_base_url="https://embedding.example.test/v1",
        embeddings_model="test-embedding-model",
        embeddings_dimensions=3,
        embeddings_batch_size=4,
    )
    monkeypatch.setattr(
        repository_routes,
        "get_embedding_configuration",
        lambda: settings,
    )

    async def no_op_worker(job_id) -> None:
        return None

    monkeypatch.setattr(repository_routes, "run_embedding_job", no_op_worker)
    first_account = create_account(api_client, "embedding-owner@example.com")
    first_headers = {"Authorization": f"Bearer {first_account['access_token']}"}
    saved_response = api_client.post(
        "/api/v1/repositories/saved",
        headers=first_headers,
        json={"repository_url": "https://github.com/Digvijay1129/RepoLens"},
    )
    assert saved_response.status_code == 201, saved_response.text
    repository_id = UUID(saved_response.json()["id"])

    with Session(api_client.app.state.test_engine) as db:
        repository = db.get(Repository, repository_id)
        repository.indexing_status = "indexed"
        repository.indexed_commit_sha = "a" * 40
        db.commit()

    response = api_client.post(
        f"/api/v1/repositories/saved/{repository_id}/embeddings",
        headers=first_headers,
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["job_type"] == "embedding"
    assert job["status"] == "queued"
    assert job["embedding_provider"] == "openai_compatible"
    assert job["embedding_model"] == "test-embedding-model"
    assert job["embedding_dimensions"] == 3

    duplicate = api_client.post(
        f"/api/v1/repositories/saved/{repository_id}/embeddings",
        headers=first_headers,
    )
    assert duplicate.status_code == 202
    assert duplicate.json()["id"] == job["id"]

    second_account = create_account(api_client, "embedding-other@example.com")
    second_headers = {"Authorization": f"Bearer {second_account['access_token']}"}
    forbidden = api_client.post(
        f"/api/v1/repositories/saved/{repository_id}/embeddings",
        headers=second_headers,
    )
    assert forbidden.status_code == 404



def test_source_search_endpoint_returns_line_citations_and_is_owner_scoped(
    api_client: TestClient,
    monkeypatch,
) -> None:
    owner = create_account(api_client, "search-owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    saved = api_client.post(
        "/api/v1/repositories/saved",
        headers=owner_headers,
        json={"repository_url": "https://github.com/Digvijay1129/RepoLens"},
    )
    assert saved.status_code == 201, saved.text
    repository_id = UUID(saved.json()["id"])
    commit_sha = "a" * 40

    with Session(api_client.app.state.test_engine) as db:
        repository = db.get(Repository, repository_id)
        repository.indexing_status = "indexed"
        repository.indexed_commit_sha = commit_sha
        db.commit()

    async def fake_search(db, repository, user_id, query, *, mode="hybrid", limit=8):
        assert repository.id == repository_id
        assert repository.user_id == user_id
        assert query == "authenticate_user"
        assert mode == "keyword"
        return {
            "repository_id": repository.id,
            "repository": repository.full_name,
            "query": query,
            "mode": mode,
            "commit_sha": commit_sha,
            "result_count": 1,
            "results": [{
                "chunk_id": UUID("00000000-0000-0000-0000-000000000123"),
                "file_path": "backend/app/auth.py",
                "language": "python",
                "start_line": 12,
                "end_line": 28,
                "symbol_names": ["authenticate_user"],
                "snippet": "def authenticate_user(token): return user",
                "score": 1.0,
                "match_types": ["keyword"],
                "commit_sha": commit_sha,
                "citation_url": f"https://github.com/Digvijay1129/RepoLens/blob/{commit_sha}/backend/app/auth.py#L12-L28",
            }],
        }

    monkeypatch.setattr(repository_routes, "search_repository_chunks", fake_search)
    response = api_client.post(
        f"/api/v1/repositories/saved/{repository_id}/search",
        headers=owner_headers,
        json={"query": "authenticate_user", "mode": "keyword", "limit": 5},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result_count"] == 1
    assert body["results"][0]["start_line"] == 12
    assert body["results"][0]["citation_url"].endswith("#L12-L28")

    another_account = create_account(api_client, "search-other@example.com")
    other_headers = {"Authorization": f"Bearer {another_account['access_token']}"}
    forbidden = api_client.post(
        f"/api/v1/repositories/saved/{repository_id}/search",
        headers=other_headers,
        json={"query": "authenticate_user", "mode": "keyword", "limit": 5},
    )
    assert forbidden.status_code == 404


def test_repository_chat_endpoint_returns_citations_and_checks_repository_ownership(
    api_client: TestClient,
    monkeypatch,
) -> None:
    owner = create_account(api_client, "rag-owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    saved = api_client.post(
        "/api/v1/repositories/saved",
        headers=owner_headers,
        json={"repository_url": "https://github.com/Digvijay1129/RepoLens"},
    )
    assert saved.status_code == 201, saved.text
    repository_id = UUID(saved.json()["id"])
    conversation_id = UUID("00000000-0000-0000-0000-000000000081")
    user_message_id = UUID("00000000-0000-0000-0000-000000000082")
    assistant_message_id = UUID("00000000-0000-0000-0000-000000000083")
    commit_sha = "c" * 40
    now = datetime(2026, 10, 25, tzinfo=timezone.utc)
    source = {
        "id": "S1",
        "file_path": "backend/app/auth.py",
        "language": "python",
        "start_line": 12,
        "end_line": 28,
        "symbol_names": ["authenticate_user"],
        "score": 0.95,
        "match_types": ["keyword"],
        "commit_sha": commit_sha,
        "citation_url": f"https://github.com/Digvijay1129/RepoLens/blob/{commit_sha}/backend/app/auth.py#L12-L28",
    }

    async def fake_chat(db, repository, user_id, message, *, conversation_id=None):
        assert repository.id == repository_id
        assert repository.user_id == user_id
        assert message == "How is auth validated?"
        return {
            "id": conversation_id or UUID("00000000-0000-0000-0000-000000000081"),
            "repository_id": repository.id,
            "title": "How is auth validated?",
            "created_at": now,
            "updated_at": now,
            "answer": "The authentication helper validates the token [S1].",
            "retrieval_mode": "keyword",
            "commit_sha": commit_sha,
            "sources": [source],
            "user_message": {
                "id": user_message_id,
                "conversation_id": conversation_id or UUID("00000000-0000-0000-0000-000000000081"),
                "role": "user",
                "content": message,
                "sources": [],
                "created_at": now,
            },
            "assistant_message": {
                "id": assistant_message_id,
                "conversation_id": conversation_id or UUID("00000000-0000-0000-0000-000000000081"),
                "role": "assistant",
                "content": "The authentication helper validates the token [S1].",
                "sources": [source],
                "created_at": now,
            },
        }

    monkeypatch.setattr(repository_routes, "run_repository_chat", fake_chat)
    response = api_client.post(
        f"/api/v1/repositories/saved/{repository_id}/chat",
        headers=owner_headers,
        json={"message": "How is auth validated?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"].endswith("[S1].")
    assert body["sources"][0]["file_path"] == "backend/app/auth.py"
    assert body["sources"][0]["citation_url"].endswith("#L12-L28")
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"

    another = create_account(api_client, "rag-other@example.com")
    other_headers = {"Authorization": f"Bearer {another['access_token']}"}
    denied = api_client.post(
        f"/api/v1/repositories/saved/{repository_id}/chat",
        headers=other_headers,
        json={"message": "How is auth validated?"},
    )
    assert denied.status_code == 404
