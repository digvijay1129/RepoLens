"""API-level tests for the public GitHub repository endpoints."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.github_client import GitHubClientError, get_github_client


class FakeGitHubClient:
    async def inspect_repository(self, repository_url: str) -> dict:
        return {
            "id": 123,
            "name": "RepoLens",
            "full_name": "digvijay1129/RepoLens",
            "description": "Codebase intelligence",
            "html_url": "https://github.com/digvijay1129/RepoLens",
            "default_branch": "main",
            "language": "Python",
            "stargazers_count": 0,
            "forks_count": 0,
            "open_issues_count": 1,
            "size": 100,
            "updated_at": datetime(2026, 10, 25, tzinfo=timezone.utc).isoformat(),
            "license_name": "MIT License",
            "archived": False,
            "private": False,
        }

    async def list_directory(self, owner: str, repository: str, path=None, ref=None) -> dict:
        if path == "README.md":
            raise GitHubClientError(400, "The selected path is a file. Choose a directory to browse.")
        return {
            "full_name": f"{owner}/{repository}",
            "owner": owner,
            "repository": repository,
            "path": path or "",
            "ref": ref,
            "items": [
                {
                    "name": "backend",
                    "path": "backend",
                    "type": "dir",
                    "sha": "abc123",
                    "size": None,
                    "html_url": f"https://github.com/{owner}/{repository}/tree/main/backend",
                    "download_url": None,
                }
            ],
            "may_be_truncated": False,
            "notice": None,
        }


@pytest.fixture()
def client():
    app.dependency_overrides[get_github_client] = lambda: FakeGitHubClient()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_inspect_endpoint_returns_curated_repository_metadata(client: TestClient) -> None:
    response = client.post(
        "/api/v1/repositories/inspect",
        json={"repository_url": "https://github.com/digvijay1129/RepoLens"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["full_name"] == "digvijay1129/RepoLens"
    assert payload["private"] is False
    assert payload["license_name"] == "MIT License"
    assert "token" not in payload


def test_inspect_endpoint_rejects_lookalike_host(client: TestClient) -> None:
    response = client.post(
        "/api/v1/repositories/inspect",
        json={"repository_url": "https://github.com.evil.test/owner/repo"},
    )
    assert response.status_code == 422
    assert "secure GitHub" in response.json()["detail"]


def test_inspect_endpoint_rejects_extra_request_fields(client: TestClient) -> None:
    response = client.post(
        "/api/v1/repositories/inspect",
        json={
            "repository_url": "https://github.com/owner/repo",
            "token": "do-not-accept",
        },
    )
    assert response.status_code == 422


def test_contents_endpoint_returns_directory_listing(client: TestClient) -> None:
    response = client.get("/api/v1/repositories/digvijay1129/RepoLens/contents")
    assert response.status_code == 200
    payload = response.json()
    assert payload["full_name"] == "digvijay1129/RepoLens"
    assert payload["items"][0]["type"] == "dir"
    assert payload["items"][0]["path"] == "backend"


def test_contents_endpoint_rejects_invalid_path(client: TestClient) -> None:
    response = client.get(
        "/api/v1/repositories/org/repo/contents",
        params={"path": "../private"},
    )
    assert response.status_code == 422
