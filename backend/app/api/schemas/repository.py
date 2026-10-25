"""Request and response schemas for public GitHub repository browsing."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class RepositoryInspectRequest(BaseModel):
    """Payload used to inspect a public GitHub repository URL."""

    model_config = ConfigDict(extra="forbid")
    repository_url: str = Field(min_length=1, max_length=2048)


class RepositoryMetadata(BaseModel):
    """Safe subset of public GitHub repository metadata exposed by RepoLens."""

    id: int
    name: str
    full_name: str
    description: str | None = None
    html_url: HttpUrl
    default_branch: str
    language: str | None = None
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    size: int = 0
    updated_at: datetime
    license_name: str | None = None
    archived: bool = False
    private: bool = False


class RepositoryContentItem(BaseModel):
    """One file, directory, symlink, or submodule from a repository directory."""

    name: str
    path: str
    type: str
    sha: str
    size: int | None = None
    html_url: HttpUrl | None = None
    download_url: HttpUrl | None = None


class RepositoryContentsResponse(BaseModel):
    """Contents of one public repository directory."""

    full_name: str
    owner: str
    repository: str
    path: str
    ref: str | None = None
    items: list[RepositoryContentItem]
    may_be_truncated: bool = False
    notice: str | None = None


class SavedRepositoryResponse(BaseModel):
    """Persisted repository workspace record scoped to its owner."""

    id: uuid.UUID
    github_repository_id: int | None
    github_owner: str
    github_name: str
    full_name: str
    canonical_url: str
    description: str | None
    language: str | None
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    size: int
    license_name: str | None
    archived: bool
    default_branch: str | None
    selected_branch: str
    indexing_status: str
    embedding_status: str
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    last_embedded_at: datetime | None
    github_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BranchOption(BaseModel):
    name: str
    commit_sha: str
    protected: bool = False


class BranchListResponse(BaseModel):
    repository_id: uuid.UUID
    selected_branch: str
    default_branch: str | None
    items: list[BranchOption]
    may_be_truncated: bool = False


class SelectBranchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_branch: str = Field(min_length=1, max_length=255)



class IndexingJobResponse(BaseModel):
    """Safe status and progress of one owner-scoped indexing attempt."""

    id: uuid.UUID
    repository_id: uuid.UUID
    job_type: str
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    status: str
    attempt_count: int
    total_files: int
    processed_files: int
    skipped_files: int
    chunk_count: int
    commit_sha: str | None
    progress_message: str
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
