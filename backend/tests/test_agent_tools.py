"""Tests for Phase 2 read-only tool contracts and OpenAI-compatible function calls."""

import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.agents.tools import AgentToolError, build_agent_tool_registry
from app.agents.tools.repository_tools import (
    InspectSourceArguments,
    ListIndexedFilesArguments,
)
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

    async def handler(request: httpx.Request) -> httpx.Response:
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

    async def handler(request: httpx.Request) -> httpx.Response:
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

    async def handler(request: httpx.Request) -> httpx.Response:
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
