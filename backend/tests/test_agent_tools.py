"""Tests for Phase 2 read-only tool contracts and OpenAI-compatible function calls."""

import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.agents.tools import AgentToolContext, AgentToolError, AgentToolRegistry, build_agent_tool_registry
from app.agents.tools.registry import AgentToolDefinition
from app.agents.tools.repository_tools import (
    InspectSourceArguments,
    ListIndexedFilesArguments,
    RepositoryOverviewArguments,
    SearchCodeArguments,
    inspect_source,
    list_indexed_files,
    repository_overview,
    search_code,
)
from app.db.base import Base
from app.models.repository import Repository
from app.models.repository_chunk import RepositoryChunk
from app.models.user import User
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.services.llm import LLMProviderError
from app.services.llm_tools import complete_chat_with_tools


def test_registry_exposes_only_the_fixed_read_only_tool_allowlist():
    registry = build_agent_tool_registry()
    tools = registry.list_tools()

    assert {tool["name"] for tool in tools} == {
        "repository_overview",
        "list_indexed_files",
        "search_code",
        "inspect_source",
    }
    assert all(tool["read_only"] is True for tool in tools)

    openai_tools = registry.openai_tool_schemas()
    assert all(tool["type"] == "function" for tool in openai_tools)
    assert {tool["function"]["name"] for tool in openai_tools} == {
        "repository_overview",
        "list_indexed_files",
        "search_code",
        "inspect_source",
    }


def test_tool_argument_schemas_reject_path_traversal_and_unbounded_ranges():
    with pytest.raises(ValidationError):
        InspectSourceArguments(file_path="../../.env")

    with pytest.raises(ValidationError):
        InspectSourceArguments(file_path="backend/app.py", start_line=1, end_line=5000)

    with pytest.raises(ValidationError):
        ListIndexedFilesArguments(prefix="../backend")


def test_registry_rejects_unregistered_tools_without_fallback():
    registry = build_agent_tool_registry()
    with pytest.raises(AgentToolError):
        registry.get("execute_shell")


def test_registry_tool_schemas_are_strict_about_extra_arguments():
    registry = build_agent_tool_registry()
    inspect_tool = next(tool for tool in registry.list_tools() if tool["name"] == "inspect_source")
    assert inspect_tool["parameters"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_openai_compatible_tool_call_response_is_parsed_and_validated():
    settings = Settings(
        environment="test",
        llm_enabled=True,
        llm_api_key=SecretStr("unit-test-tool-key"),
        llm_base_url="https://provider.example.test/v1",
        llm_model="test-agent-model",
        llm_max_retries=0,
    )
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call_repo_overview",
                                    "type": "function",
                                    "function": {
                                        "name": "repository_overview",
                                        "arguments": "{}",
                                    },
                                }
                            ]
                        }
                    }
                ]
            },
        )

    result = await complete_chat_with_tools(
        [{"role": "system", "content": "Choose one tool."}],
        [
            {
                "type": "function",
                "function": {
                    "name": "repository_overview",
                    "description": "Inspect the repository.",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            }
        ],
        settings=settings,
        transport=httpx.MockTransport(handler),
    )

    assert result.call_id == "call_repo_overview"
    assert result.name == "repository_overview"
    assert result.arguments == {}
    assert observed["payload"]["tool_choice"] == "required"
    assert observed["payload"]["parallel_tool_calls"] is False


@pytest.mark.asyncio
async def test_openai_compatible_tool_call_rejects_multiple_function_calls():
    settings = Settings(
        environment="test",
        llm_enabled=True,
        llm_api_key=SecretStr("unit-test-tool-key"),
        llm_base_url="https://provider.example.test/v1",
        llm_model="test-agent-model",
        llm_max_retries=0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "one",
                                    "type": "function",
                                    "function": {"name": "repository_overview", "arguments": "{}"},
                                },
                                {
                                    "id": "two",
                                    "type": "function",
                                    "function": {"name": "inspect_source", "arguments": "{}"},
                                },
                            ]
                        }
                    }
                ]
            },
        )

    with pytest.raises(LLMProviderError, match="exactly one"):
        await complete_chat_with_tools(
            [{"role": "system", "content": "Choose one tool."}],
            [
                {
                    "type": "function",
                    "function": {
                        "name": "repository_overview",
                        "description": "Inspect the repository.",
                        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                    },
                }
            ],
            settings=settings,
            transport=httpx.MockTransport(handler),
        )


@pytest.mark.asyncio
async def test_openai_compatible_tool_call_rejects_malformed_json_arguments():
    settings = Settings(
        environment="test",
        llm_enabled=True,
        llm_api_key=SecretStr("unit-test-tool-key"),
        llm_base_url="https://provider.example.test/v1",
        llm_model="test-agent-model",
        llm_max_retries=0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "bad-json",
                                    "type": "function",
                                    "function": {
                                        "name": "repository_overview",
                                        "arguments": "{not-json",
                                    },
                                }
                            ]
                        }
                    }
                ]
            },
        )

    with pytest.raises(LLMProviderError, match="malformed JSON"):
        await complete_chat_with_tools(
            [{"role": "system", "content": "Choose one tool."}],
            [
                {
                    "type": "function",
                    "function": {
                        "name": "repository_overview",
                        "description": "Inspect the repository.",
                        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                    },
                }
            ],
            settings=settings,
            transport=httpx.MockTransport(handler),
        )



@pytest.fixture()
def indexed_tool_context():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    user = User(email="agent-tool-context@example.com")
    db.add(user)
    db.flush()
    repository = Repository(
        user_id=user.id,
        github_owner="example",
        github_name="project",
        full_name="example/project",
        canonical_url="https://github.com/example/project",
        indexing_status="indexed",
        indexed_commit_sha="a" * 40,
        selected_branch="main",
        default_branch="main",
    )
    db.add(repository)
    db.flush()
    db.add(
        RepositoryChunk(
            repository_id=repository.id,
            user_id=user.id,
            commit_sha="a" * 40,
            file_path="backend/auth.py",
            language="python",
            chunk_index=0,
            start_line=1,
            end_line=3,
            content_hash="b" * 64,
            symbol_names="login,validate_token",
            token_count=12,
            chunk_text="def login(token):\n    return validate_token(token)\n",
        )
    )
    db.commit()
    yield AgentToolContext(db=db, repository=repository, user_id=user.id)
    db.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_repository_tools_read_only_over_the_selected_indexed_snapshot(indexed_tool_context):
    context = indexed_tool_context

    overview = await repository_overview(context, RepositoryOverviewArguments())
    assert overview["repository"] == "example/project"
    assert overview["indexed_file_count"] == 1
    assert overview["indexed_chunk_count"] == 1
    assert overview["indexed_commit_sha"] == "a" * 40

    files = await list_indexed_files(
        context,
        ListIndexedFilesArguments(prefix="backend", limit=10),
    )
    assert files["result_count"] == 1
    assert files["files"][0]["file_path"] == "backend/auth.py"

    inspected = await inspect_source(
        context,
        InspectSourceArguments(file_path="backend/auth.py", start_line=1, end_line=2),
    )
    assert inspected["returned_line_count"] == 2
    assert "1: def login(token):" in inspected["source"]
    assert "2:     return validate_token(token)" in inspected["source"]
    assert "blob/" + "a" * 40 in inspected["citation_url"]

    found = await search_code(
        context,
        SearchCodeArguments(query="validate_token", mode="keyword", limit=5),
    )
    assert found["result_count"] == 1
    assert found["results"][0]["chunk_id"]


@pytest.mark.asyncio
async def test_repository_tool_cannot_read_another_users_repository(indexed_tool_context):
    context = indexed_tool_context
    from uuid import uuid4

    other_context = AgentToolContext(
        db=context.db,
        repository=context.repository,
        user_id=uuid4(),
    )
    with pytest.raises(AgentToolError, match="not found"):
        await repository_overview(other_context, RepositoryOverviewArguments())


def test_tool_registry_rejects_non_read_only_registration():
    registry = AgentToolRegistry()

    async def unsafe_handler(context, arguments):
        return {"executed": True}

    with pytest.raises(ValueError, match="Only read-only tools"):
        registry.register(
            AgentToolDefinition(
                name="modify_repository",
                description="Modify source files.",
                arguments_model=RepositoryOverviewArguments,
                handler=unsafe_handler,
                read_only=False,
            )
        )
