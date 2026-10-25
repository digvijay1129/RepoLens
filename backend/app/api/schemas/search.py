"""Pydantic schemas for versioned source retrieval."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RepositorySearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=2, max_length=500)
    mode: Literal["keyword", "semantic", "hybrid"] = "hybrid"
    limit: int = Field(default=8, ge=1, le=20)


class RepositorySearchResult(BaseModel):
    chunk_id: uuid.UUID
    file_path: str
    language: str
    start_line: int
    end_line: int
    symbol_names: list[str]
    snippet: str
    score: float = Field(ge=0, le=1)
    match_types: list[Literal["semantic", "keyword"]]
    commit_sha: str
    citation_url: str


class RepositorySearchResponse(BaseModel):
    repository_id: uuid.UUID
    repository: str
    query: str
    mode: Literal["keyword", "semantic", "hybrid"]
    commit_sha: str
    result_count: int
    results: list[RepositorySearchResult]
