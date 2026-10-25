"""Unit tests for safe GitHub URL, metadata, and directory handling."""

import json

import httpx
import pytest

from app.services.github_client import (
    GitHubClientError,
    GitHubPublicClient,
    normalize_directory_path,
    parse_public_repository_url,
)


@pytest.mark.parametrize(
    ("url", "expected_owner", "expected_repository"),
    [
        ("https://github.com/digvijay1129/RepoLens", "digvijay1129", "RepoLens"),
        (" https://github.com/org/repository.git/ ", "org", "repository"),
        ("https://github.com/owner/repo/", "owner", "repo"),
    ],
)
def test_parse_public_repository_url(url, expected_owner, expected_repository) -> None:
    result = parse_public_repository_url(url)
    assert result["owner"] == expected_owner
    assert result["repository"] == expected_repository
    assert result["canonical_url"] == f"https://github.com/{expected_owner}/{expected_repository}"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a URL",
        "http://github.com/owner/repo",
        "https://github.com.evil.test/owner/repo",
        "https://github.com/owner/repo/issues",
        "https://github.com/owner/repo?tab=readme",
        "https://github.com/owner/repo#readme",
        "https://user@github.com/owner/repo",
        "https://github.com/owner/%2Frepo",
        "https://github.com/owner/..",
        "https://github.com/-owner/repo",
    ],
)
def test_parse_public_repository_url_rejects_unsafe_input(url) -> None:
    with pytest.raises(ValueError):
        parse_public_repository_url(url)


def test_normalize_directory_path_accepts_repository_relative_paths() -> None:
    assert normalize_directory_path(None) == ""
    assert normalize_directory_path("src/api/") == "src/api"


@pytest.mark.parametrize("path", ["/etc/passwd", "../README.md", "src/../secret", "src\\..\\secret", "src//file.py", "./src"])
def test_normalize_directory_path_rejects_unsafe_paths(path) -> None:
    with pytest.raises(ValueError):
        normalize_directory_path(path)


@pytest.mark.asyncio
async def test_inspect_repository_returns_curated_public_metadata() -> None:
    payload = {
        "id": 42,
        "name": "RepoLens",
        "full_name": "digvijay1129/RepoLens",
        "description": "Codebase intelligence",
        "html_url": "https://github.com/digvijay1129/RepoLens",
        "default_branch": "main",
        "language": "Python",
        "stargazers_count": 3,
        "forks_count": 1,
        "open_issues_count": 2,
        "size": 128,
        "updated_at": "2026-10-25T00:00:00Z",
        "license": {"name": "MIT License"},
        "archived": False,
        "private": False,
        "owner": {"token": "must not pass through"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.github.com"
        assert request.url.path == "/repos/digvijay1129/RepoLens"
        return httpx.Response(200, json=payload, request=request)

    async with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        result = await client.inspect_repository("https://github.com/digvijay1129/RepoLens")

    assert result["full_name"] == "digvijay1129/RepoLens"
    assert result["license_name"] == "MIT License"
    assert result["private"] is False
    assert "owner" not in result


@pytest.mark.asyncio
async def test_inspect_rejects_private_repository_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"private": True}, request=request)

    async with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GitHubClientError) as error:
            await client.inspect_repository("https://github.com/owner/repo")

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_list_directory_encodes_path_and_branch_as_data() -> None:
    payload = [
        {
            "name": "main.py",
            "path": "src/main.py",
            "type": "file",
            "sha": "abc123",
            "size": 25,
            "html_url": "https://github.com/org/repo/blob/main/src/main.py",
            "download_url": "https://raw.githubusercontent.com/org/repo/main/src/main.py",
        },
        {
            "name": "tests",
            "path": "tests",
            "type": "dir",
            "sha": "def456",
            "size": None,
            "html_url": "https://github.com/org/repo/tree/main/tests",
            "download_url": None,
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path.startswith(b"/repos/org/repo/contents/src%20files?")
        assert request.url.params["ref"] == "feature/one"
        return httpx.Response(200, json=payload, request=request)

    async with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        result = await client.list_directory("org", "repo", path="src files", ref="feature/one")

    assert result["path"] == "src files"
    assert [item["type"] for item in result["items"]] == ["file", "dir"]


@pytest.mark.asyncio
async def test_list_directory_rejects_file_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"type": "file"}, request=request)

    async with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GitHubClientError) as error:
            await client.list_directory("org", "repo", path="README.md")

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_github_rate_limit_is_a_retryable_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1234567890"},
            json={"message": "API rate limit exceeded"},
            request=request,
        )

    async with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GitHubClientError) as error:
            await client.inspect_repository("https://github.com/org/repo")

    assert error.value.status_code == 429
    assert "rate limit" in error.value.detail.lower()


@pytest.mark.asyncio
async def test_github_upstream_server_error_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="internal upstream error", request=request)

    async with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GitHubClientError) as error:
            await client.inspect_repository("https://github.com/org/repo")

    assert error.value.status_code == 502
    assert "internal upstream error" not in error.value.detail

@pytest.mark.asyncio
async def test_list_branches_returns_safe_branch_names_and_commit_shas() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/org/repo/branches"
        assert request.url.params["per_page"] == "100"
        assert request.url.params["page"] == "1"
        return httpx.Response(
            200,
            json=[
                {
                    "name": "main",
                    "commit": {"sha": "a" * 40},
                    "protected": True,
                    "protection": {"secret": "not-returned"},
                },
                {
                    "name": "feature/add-tests",
                    "commit": {"sha": "b" * 40},
                    "protected": False,
                },
            ],
            request=request,
        )

    async with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        branches = await client.list_branches("org", "repo")

    assert branches == [
        {"name": "main", "commit_sha": "a" * 40, "protected": True},
        {"name": "feature/add-tests", "commit_sha": "b" * 40, "protected": False},
    ]
