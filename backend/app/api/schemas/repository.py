"""Request and response schemas for public GitHub repository browsing."""

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
