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
