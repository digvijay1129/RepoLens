"""Public GitHub browsing plus authenticated, owner-scoped repository management."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.schemas.repository import (
    BranchListResponse,
    BranchOption,
    RepositoryContentsResponse,
    RepositoryInspectRequest,
    RepositoryMetadata,
    SavedRepositoryResponse,
    SelectBranchRequest,
)
from app.db.session import get_db_session
from app.models.repository import Repository
from app.models.user import User
from app.services.github_client import (
    GitHubClientError,
    GitHubPublicClient,
    get_github_client,
    normalize_directory_path,
    parse_public_repository_url,
    validate_repository_locator,
)

router = APIRouter()


def _raise_github_error(error: GitHubClientError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


def _saved_repository_payload(repository: Repository) -> dict:
    """Build a safe API representation, preserving display casing from GitHub."""
    return {
        "id": repository.id,
        "github_repository_id": repository.github_repository_id,
        "github_owner": repository.github_owner,
        "github_name": repository.github_name,
        "full_name": f"{repository.github_owner}/{repository.github_name}",
        "canonical_url": repository.canonical_url,
        "description": repository.description,
        "language": repository.language,
        "stargazers_count": repository.stargazers_count,
        "forks_count": repository.forks_count,
        "open_issues_count": repository.open_issues_count,
        "size": repository.size,
        "license_name": repository.license_name,
        "archived": repository.archived,
        "default_branch": repository.default_branch,
        "selected_branch": repository.selected_branch,
        "indexing_status": repository.indexing_status,
        "github_updated_at": repository.github_updated_at,
        "created_at": repository.created_at,
        "updated_at": repository.updated_at,
    }


def _get_owned_repository(
    db: Session,
    repository_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Repository:
    """Always scope a saved-repository lookup to its authenticated owner."""
    repository = db.scalar(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == user_id,
        )
    )
    if repository is None:
        # Use the same response for unknown IDs and other users' IDs.
        raise HTTPException(status_code=404, detail="Saved repository was not found.")
    return repository


def _to_datetime(value: datetime | str | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


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
        raise HTTPException(
            status_code=502,
            detail="GitHub returned incomplete repository metadata.",
        ) from exc


@router.post(
    "/saved",
    response_model=SavedRepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect and persist a public repository for the current user",
)
async def save_repository(
    body: RepositoryInspectRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    github: Annotated[GitHubPublicClient, Depends(get_github_client)],
) -> SavedRepositoryResponse:
    """Re-fetch metadata from GitHub and save it only to the authenticated user's workspace."""
    try:
        locator = parse_public_repository_url(body.repository_url)
        metadata = RepositoryMetadata.model_validate(
            await github.inspect_repository(body.repository_url)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GitHubClientError as exc:
        _raise_github_error(exc)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="GitHub returned incomplete repository metadata.",
        ) from exc

    parts = metadata.full_name.split("/", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=502, detail="GitHub returned an invalid repository name.")

    owner_name, repository_name = parts
    normalized_full_name = metadata.full_name.lower()
    repository = db.scalar(
        select(Repository).where(
            Repository.user_id == current_user.id,
            Repository.full_name == normalized_full_name,
        )
    )
    is_new = repository is None
    if repository is None:
        repository = Repository(
            user_id=current_user.id,
            github_owner=owner_name,
            github_name=repository_name,
            full_name=normalized_full_name,
            canonical_url=str(metadata.html_url),
            selected_branch=metadata.default_branch or "main",
        )
        db.add(repository)

    repository.github_repository_id = metadata.id
    repository.github_owner = owner_name
    repository.github_name = repository_name
    repository.full_name = normalized_full_name
    repository.canonical_url = str(metadata.html_url)
    repository.description = metadata.description
    repository.language = metadata.language
    repository.stargazers_count = metadata.stargazers_count
    repository.forks_count = metadata.forks_count
    repository.open_issues_count = metadata.open_issues_count
    repository.size = metadata.size
    repository.license_name = metadata.license_name
    repository.archived = metadata.archived
    repository.github_updated_at = _to_datetime(metadata.updated_at)
    repository.default_branch = metadata.default_branch
    if not repository.selected_branch:
        repository.selected_branch = metadata.default_branch or "main"

    try:
        db.commit()
        db.refresh(repository)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The repository could not be saved because it conflicts with an existing record.",
        ) from exc

    return SavedRepositoryResponse.model_validate(_saved_repository_payload(repository))


@router.get(
    "/saved",
    response_model=list[SavedRepositoryResponse],
    summary="List saved repositories for the current user",
)
def list_saved_repositories(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[SavedRepositoryResponse]:
    """Return only repositories owned by the authenticated user."""
    repositories = db.scalars(
        select(Repository)
        .where(Repository.user_id == current_user.id)
        .order_by(Repository.updated_at.desc(), Repository.created_at.desc())
    ).all()
    return [
        SavedRepositoryResponse.model_validate(_saved_repository_payload(repository))
        for repository in repositories
    ]


@router.delete(
    "/saved/{repository_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a saved repository from the current user's workspace",
)
def delete_saved_repository(
    repository_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> Response:
    """Delete only a repository whose owner ID matches the authenticated user."""
    repository = _get_owned_repository(db, repository_id, current_user.id)
    db.delete(repository)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/saved/{repository_id}/branches",
    response_model=BranchListResponse,
    summary="List public branches for a saved repository",
)
async def list_saved_repository_branches(
    repository_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    github: Annotated[GitHubPublicClient, Depends(get_github_client)],
) -> BranchListResponse:
    """Resolve repository ownership before asking GitHub for branch metadata."""
    repository = _get_owned_repository(db, repository_id, current_user.id)
    try:
        branches = await github.list_branches(repository.github_owner, repository.github_name)
    except GitHubClientError as exc:
        _raise_github_error(exc)
    items = [BranchOption.model_validate(branch) for branch in branches]
    return BranchListResponse(
        repository_id=repository.id,
        selected_branch=repository.selected_branch,
        default_branch=repository.default_branch,
        items=items,
        may_be_truncated=len(items) >= 500,
    )


@router.patch(
    "/saved/{repository_id}/branch",
    response_model=SavedRepositoryResponse,
    summary="Persist the selected branch for the current user",
)
async def select_saved_repository_branch(
    repository_id: uuid.UUID,
    body: SelectBranchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    github: Annotated[GitHubPublicClient, Depends(get_github_client)],
) -> SavedRepositoryResponse:
    """Change a branch only after confirming it is a branch in the owned public repository."""
    repository = _get_owned_repository(db, repository_id, current_user.id)
    branch_name = body.selected_branch.strip()
    if (
        not branch_name
        or len(branch_name) > 255
        or any(ord(character) < 32 or ord(character) == 127 for character in branch_name)
    ):
        raise HTTPException(status_code=422, detail="The selected branch name is invalid.")

    try:
        branches = await github.list_branches(repository.github_owner, repository.github_name)
    except GitHubClientError as exc:
        _raise_github_error(exc)

    if not any(branch["name"] == branch_name for branch in branches):
        raise HTTPException(
            status_code=422,
            detail="The selected branch was not found in the repository's available branch list.",
        )

    repository.selected_branch = branch_name
    db.commit()
    db.refresh(repository)
    return SavedRepositoryResponse.model_validate(_saved_repository_payload(repository))


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
        owner, repository = validate_repository_locator(owner, repository)
        normalized_path = normalize_directory_path(path)
        if ref is not None and (
            not ref.strip()
            or len(ref) > 255
            or any(ord(character) < 32 or ord(character) == 127 for character in ref)
        ):
            raise ValueError("The branch or ref is invalid.")
        payload = await github.list_directory(
            owner, repository, path=normalized_path, ref=ref
        )
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
