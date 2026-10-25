"""Safe, public-only GitHub REST client for RepoLens.

The API host is fixed to api.github.com; callers cannot supply arbitrary hosts.
This client does not use credentials, download file contents, or execute source.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
OWNER_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
MAX_DIRECTORY_ITEMS = 1000


class GitHubClientError(RuntimeError):
    """Safe, user-displayable GitHub integration error."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def parse_public_repository_url(value: str) -> dict[str, str]:
    """Validate and canonicalize a public github.com owner/repository URL."""
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise ValueError("Enter a GitHub repository URL.")

    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Enter a valid GitHub repository URL.") from exc

    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != "github.com"
        or (port is not None and port != 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Use a secure GitHub repository URL without credentials or query parameters."
        )

    path = parsed.path[:-1] if parsed.path.endswith("/") else parsed.path
    segments = path.split("/")[1:]
    if not path.startswith("/") or len(segments) != 2 or any(not part for part in segments):
        raise ValueError("Enter a repository URL with exactly an owner and repository name.")

    try:
        owner, repository = (unquote(segment, errors="strict") for segment in segments)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("The repository URL contains invalid encoded characters.") from exc

    if any(
        "/" in part or chr(92) in part or any(ord(character) < 32 for character in part)
        for part in (owner, repository)
    ):
        raise ValueError("The repository URL contains an invalid path segment.")

    if not OWNER_PATTERN.fullmatch(owner):
        raise ValueError("The GitHub owner name is not valid.")

    if repository.lower().endswith(".git"):
        repository = repository[:-4]
    if (
        not REPOSITORY_PATTERN.fullmatch(repository)
        or not any(character.isalnum() for character in repository)
        or ".." in repository
    ):
        raise ValueError("The GitHub repository name is not valid.")

    return {
        "owner": owner,
        "repository": repository,
        "canonical_url": f"https://github.com/{owner}/{repository}",
    }


def validate_repository_locator(owner: str, repository: str) -> tuple[str, str]:
    """Validate owner/repository path parameters independently of URL parsing."""
    if not OWNER_PATTERN.fullmatch(owner):
        raise ValueError("The GitHub owner name is not valid.")
    if (
        not REPOSITORY_PATTERN.fullmatch(repository)
        or not any(character.isalnum() for character in repository)
        or ".." in repository
    ):
        raise ValueError("The GitHub repository name is not valid.")
    return owner, repository


def normalize_directory_path(value: str | None) -> str:
    """Validate a repository-relative directory path and normalize it."""
    if value is None or value == "":
        return ""
    if len(value) > 2000:
        raise ValueError("The repository path is too long.")
    if value.startswith("/") or chr(92) in value or chr(0) in value:
        raise ValueError("Use a repository-relative path.")

    path = value[:-1] if value.endswith("/") else value
    parts = path.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise ValueError("The repository path contains an invalid segment.")
    if any(any(ord(character) < 32 or ord(character) == 127 for character in part) for part in parts):
        raise ValueError("The repository path contains unsupported characters.")
    return path


class GitHubPublicClient:
    """Small async client for metadata and directory listing of public repos."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "GitHubPublicClient":
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "User-Agent": "RepoLens",
            },
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=False,
            transport=self._transport,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        if self._client is None:
            raise RuntimeError("GitHubPublicClient must be used inside an async context manager.")

        try:
            response = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise GitHubClientError(502, "GitHub did not respond in time. Please retry.") from exc
        except httpx.RequestError as exc:
            raise GitHubClientError(502, "Unable to reach GitHub. Please retry shortly.") from exc

        if response.status_code == 404:
            raise GitHubClientError(404, "Public GitHub repository or path was not found.")
        if response.status_code == 429 or (
            response.status_code == 403
            and response.headers.get("X-RateLimit-Remaining") == "0"
        ):
            reset = response.headers.get("X-RateLimit-Reset")
            message = "GitHub API rate limit reached. Please retry later."
            if reset and reset.isdigit():
                message += f" Rate limit reset timestamp: {reset}."
            raise GitHubClientError(429, message)
        if response.status_code == 403:
            raise GitHubClientError(502, "GitHub denied this public API request.")
        if response.status_code >= 500:
            raise GitHubClientError(502, "GitHub is temporarily unavailable. Please retry.")
        if response.status_code < 200 or response.status_code >= 300:
            raise GitHubClientError(502, "GitHub returned an unexpected response.")

        try:
            return response.json()
        except ValueError as exc:
            raise GitHubClientError(502, "GitHub returned an unexpected response.") from exc

    async def inspect_repository(self, repository_url: str) -> dict[str, Any]:
        """Return a curated metadata payload for a validated public repository."""
        locator = parse_public_repository_url(repository_url)
        payload = await self._get_json(
            f"/repos/{quote(locator['owner'], safe='')}/{quote(locator['repository'], safe='')}"
        )
        if not isinstance(payload, dict) or payload.get("private") is True:
            raise GitHubClientError(404, "Public GitHub repository was not found.")

        license_payload = payload.get("license")
        license_name = license_payload.get("name") if isinstance(license_payload, dict) else None

        # Explicitly curate the fields returned by the API; do not pass through
        # owner objects, permissions, tokens, URLs supplied by other sources, or arbitrary data.
        return {
            "id": payload.get("id"),
            "name": payload.get("name"),
            "full_name": payload.get("full_name"),
            "description": payload.get("description"),
            "html_url": payload.get("html_url"),
            "default_branch": payload.get("default_branch"),
            "language": payload.get("language"),
            "stargazers_count": payload.get("stargazers_count", 0),
            "forks_count": payload.get("forks_count", 0),
            "open_issues_count": payload.get("open_issues_count", 0),
            "size": payload.get("size", 0),
            "updated_at": payload.get("updated_at"),
            "license_name": license_name,
            "archived": payload.get("archived", False),
            "private": False,
        }

    async def list_directory(
        self,
        owner: str,
        repository: str,
        path: str | None = None,
        ref: str | None = None,
    ) -> dict[str, Any]:
        """List one public repository directory without fetching file contents."""
        owner, repository = validate_repository_locator(owner, repository)
        normalized_path = normalize_directory_path(path)
        if ref is not None and (
            not ref.strip()
            or len(ref) > 255
            or any(ord(character) < 32 or ord(character) == 127 for character in ref)
        ):
            raise ValueError("The branch or ref is invalid.")

        encoded_path = (
            "/".join(quote(segment, safe="") for segment in normalized_path.split("/"))
            if normalized_path else ""
        )
        endpoint = (
            f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}/contents"
            + (f"/{encoded_path}" if encoded_path else "")
        )
        payload = await self._get_json(endpoint, params={"ref": ref} if ref is not None else None)

        if not isinstance(payload, list):
            if isinstance(payload, dict) and payload.get("type") == "file":
                raise GitHubClientError(400, "The selected path is a file. Choose a directory to browse.")
            raise GitHubClientError(502, "GitHub returned an unexpected directory listing.")

        items: list[dict[str, Any]] = []
        for item in payload[:MAX_DIRECTORY_ITEMS]:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type not in {"file", "dir", "symlink", "submodule"}:
                item_type = "unknown"
            items.append(
                {
                    "name": item.get("name", ""),
                    "path": item.get("path", ""),
                    "type": item_type,
                    "sha": item.get("sha", ""),
                    "size": item.get("size") if isinstance(item.get("size"), int) else None,
                    "html_url": item.get("html_url"),
                    "download_url": item.get("download_url"),
                }
            )

        may_be_truncated = len(payload) >= MAX_DIRECTORY_ITEMS
        return {
            "owner": owner,
            "repository": repository,
            "full_name": f"{owner}/{repository}",
            "path": normalized_path,
            "ref": ref,
            "items": items,
            "may_be_truncated": may_be_truncated,
            "notice": (
                "GitHub may truncate directory listings at 1,000 entries."
                if may_be_truncated else None
            ),
        }


async def get_github_client() -> AsyncIterator[GitHubPublicClient]:
    """FastAPI dependency that always closes the GitHub HTTP client."""
    async with GitHubPublicClient() as client:
        yield client
