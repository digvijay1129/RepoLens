"""Pydantic schemas for repository-grounded RAG chat and conversation history."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RepositoryChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=2, max_length=4000)
    conversation_id: uuid.UUID | None = None


class ChatSource(BaseModel):
    id: str = Field(pattern=r"^S[1-9][0-9]*$")
    file_path: str
    language: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    symbol_names: list[str] = Field(default_factory=list)
    score: float = Field(ge=0, le=1)
    match_types: list[str]
    commit_sha: str
    citation_url: str


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class ChatConversationSummary(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ChatConversationHistory(ChatConversationSummary):
    messages: list[ChatMessageResponse]


class ChatConversationListResponse(BaseModel):
    repository_id: uuid.UUID
    items: list[ChatConversationSummary]


class RepositoryChatResponse(ChatConversationSummary):
    answer: str
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    sources: list[ChatSource]
    retrieval_mode: str
    commit_sha: str | None = None
