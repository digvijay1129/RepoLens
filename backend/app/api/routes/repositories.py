"""Public GitHub repository inspection and directory browsing routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from app.api.schemas.repository import (
    RepositoryContentsResponse,
    RepositoryInspectRequest,
    RepositoryMetadata,
)
from app.services.github_client import (
    GitHubClientError,
    GitHubPublicClient,
    get_github_client,
    parse_public_repository_url,
)

router = APIRouter()


def _raise_github_error(error: GitHubClientError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    "/inspect",
    response_model=RepositoryMetadata,
    summary="Inspect a public GitHub repository",
)
async def inspect_repository(
    body: RepositoryInspectRequest,
    github: Annotated[GitHubPublicClient, Depends(get_github_client)],
) -> RepositoryMetadata:
    """Validate the URL and fetch public metadata from GitHub's API."""
    try:
        parse_public_repository_url(body.repository_url)
        payload = await github.inspect_repository(body.repository_url)
        return RepositoryMetadata.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GitHubClientError as exc:
        _raise_github_error(exc)
    except ValidationError as exc:
        # A malformed upstream response should not leak internals to the client.
        raise HTTPException(
            status_code=502,
            detail="GitHub returned incomplete repository metadata.",
        ) from exc


@router.get(
    "/{owner}/{repository}/contents",
    response_model=RepositoryContentsResponse,
    summary="List a public GitHub repository directory",
)
async def list_repository_contents(
    owner: str,
    repository: str,
    github: Annotated[GitHubPublicClient, Depends(get_github_client)],
    path: Annotated[str | None, Query(max_length=2000)] = None,
    ref: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
) -> RepositoryContentsResponse:
    """List directory entries and GitHub source links without returning file contents."""
    try:
        payload = await github.list_directory(owner, repository, path=path, ref=ref)
        return RepositoryContentsResponse.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GitHubClientError as exc:
        _raise_github_error(exc)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="GitHub returned an unexpected directory response.",
        ) from exc
