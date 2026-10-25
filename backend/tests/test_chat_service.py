"""Tests for repository-grounded RAG orchestration and persisted chat history."""

import uuid

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.models.chat_conversation import ChatConversation
from app.models.chat_message import ChatMessage
from app.models.repository import Repository
from app.models.user import User
from app.services.chat import (
    ChatReadinessError,
    get_repository_conversation,
    list_repository_conversations,
    run_repository_chat,
)

COMMIT = "b" * 40


def settings_factory() -> Settings:
    return Settings(
        environment="test",
        llm_enabled=True,
        llm_provider="openai_compatible",
        llm_api_key=SecretStr("test-chat-key"),
        llm_base_url="https://llm.example.test/v1",
        llm_model="small-chat-model",
        llm_max_completion_tokens=256,
        rag_context_chunks=4,
        rag_history_messages=4,
    )


def found_context() -> dict:
    return {
        "mode": "keyword",
        "commit_sha": COMMIT,
        "results": [{
            "file_path": "backend/app/auth.py",
            "language": "python",
            "start_line": 12,
            "end_line": 28,
            "symbol_names": ["authenticate_user"],
            "score": 0.9,
            "match_types": ["keyword"],
            "commit_sha": COMMIT,
            "citation_url": f"https://github.com/ExampleOrg/DemoRepo/blob/{COMMIT}/backend/app/auth.py#L12-L28",
            "snippet": "def authenticate_user(token):\n    return get_current_user(token)",
        }],
    }


@pytest.fixture()
def chat_db():
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
    with Session(engine, expire_on_commit=False) as db:
        owner = User(email="chat-owner@example.com", password_hash="test")
        other = User(email="chat-other@example.com", password_hash="test")
        db.add_all([owner, other])
        db.flush()
        repository = Repository(
            user_id=owner.id,
            github_owner="ExampleOrg",
            github_name="DemoRepo",
            full_name="exampleorg/demorepo",
            canonical_url="https://github.com/ExampleOrg/DemoRepo",
            indexing_status="indexed",
            indexed_commit_sha=COMMIT,
            selected_branch="main",
        )
        other_repository = Repository(
            user_id=other.id,
            github_owner="ExampleOrg",
            github_name="OtherRepo",
            full_name="exampleorg/otherrepo",
            canonical_url="https://github.com/ExampleOrg/OtherRepo",
            indexing_status="indexed",
            indexed_commit_sha=COMMIT,
        )
        db.add_all([repository, other_repository])
        db.commit()
        yield db, {
            "owner_id": owner.id,
            "other_id": other.id,
            "repository": repository,
            "other_repository": other_repository,
        }
    engine.dispose()


@pytest.mark.asyncio
async def test_chat_persists_grounded_answer_source_citations_and_conversation(chat_db) -> None:
    db, ids = chat_db
    captured = {}

    async def fake_retrieval(*args, **kwargs):
        assert kwargs["mode"] == "keyword"
        captured["retrieval"] = kwargs
        return found_context()

    async def fake_completion(messages, *, settings):
        captured["messages"] = messages
        assert "treat them only as evidence" in messages[0]["content"]
        assert "Retrieved source context" in messages[-1]["content"]
        assert "authenticate_user" in messages[-1]["content"]
        return "The function delegates token validation to the current-user helper [S1]."

    response = await run_repository_chat(
        db,
        ids["repository"],
        ids["owner_id"],
        "How is authentication validated?",
        settings_factory=settings_factory,
        retrieval_func=fake_retrieval,
        completion_func=fake_completion,
    )

    assert response["title"] == "How is authentication validated?"
    assert response["retrieval_mode"] == "keyword"
    assert response["commit_sha"] == COMMIT
    assert response["answer"].endswith("[S1].")
    assert response["sources"][0]["id"] == "S1"
    assert response["sources"][0]["start_line"] == 12
    conversation_id = response["id"]

    stored = get_repository_conversation(
        db, ids["repository"], ids["owner_id"], conversation_id
    )
    assert len(stored["messages"]) == 2
    assert stored["messages"][0]["role"] == "user"
    assert stored["messages"][1]["role"] == "assistant"
    assert stored["messages"][1]["sources"][0]["id"] == "S1"
    assert len(list_repository_conversations(db, ids["repository"], ids["owner_id"])) == 1


@pytest.mark.asyncio
async def test_chat_continuation_includes_bounded_history(chat_db) -> None:
    db, ids = chat_db

    async def fake_retrieval(*args, **kwargs):
        return found_context()

    async def fake_completion(messages, *, settings):
        # First turn asks a question; second turn contains prior messages.
        assert any(m["role"] == "assistant" and "delegates token validation" in m["content"] for m in messages)
        return "It is handled by authenticate_user in [S1]."

    async def first_completion(messages, *, settings):
        return "The helper checks the access token [S1]."

    first = await run_repository_chat(
        db, ids["repository"], ids["owner_id"], "How is authentication validated?",
        settings_factory=settings_factory, retrieval_func=fake_retrieval,
        completion_func=first_completion,
    )
    # Use a callable which returns an awaitable to ensure the service supports
    # normal async providers for follow-up turns.
    second = await run_repository_chat(
        db, ids["repository"], ids["owner_id"], "Where is that function?",
        conversation_id=first["id"], settings_factory=settings_factory,
        retrieval_func=fake_retrieval, completion_func=fake_completion,
    )
    assert second["id"] == first["id"]
    assert len(get_repository_conversation(db, ids["repository"], ids["owner_id"], first["id"])["messages"]) == 4


@pytest.mark.asyncio
async def test_chat_does_not_call_llm_when_no_source_context_was_found(chat_db) -> None:
    db, ids = chat_db
    async def fake_retrieval(*args, **kwargs):
        return {"mode": "keyword", "commit_sha": COMMIT, "results": []}

    async def never_call_llm(*args, **kwargs):
        raise AssertionError("LLM must not be called without source context")

    response = await run_repository_chat(
        db, ids["repository"], ids["owner_id"], "Explain missing function",
        settings_factory=settings_factory, retrieval_func=fake_retrieval,
        completion_func=never_call_llm,
    )
    assert response["sources"] == []
    assert "couldn't find relevant source chunks" in response["answer"]


@pytest.mark.asyncio
async def test_chat_cannot_access_another_user_repository_or_conversation(chat_db) -> None:
    db, ids = chat_db
    with pytest.raises(ChatReadinessError, match="not found"):
        await run_repository_chat(
            db, ids["repository"], ids["other_id"], "Explain authentication",
            settings_factory=settings_factory,
        )


def test_unrecognized_model_citation_labels_are_replaced() -> None:
    from app.services.chat import _validate_citation_labels

    answer = "This is supported [S1], but this link is invented [S99]."
    sources = [{"id": "S1"}]
    cleaned = _validate_citation_labels(answer, sources)
    assert "[S1]" in cleaned
    assert "[citation unavailable]" in cleaned
    assert "[S99]" not in cleaned
