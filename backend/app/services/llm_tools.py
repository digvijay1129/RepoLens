"""OpenAI-compatible function/tool-call completion support for RepoLens agents."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import Settings
from app.services.llm import (
    LLMConfigurationError,
    LLMProviderError,
    get_llm_configuration,
)


@dataclass(frozen=True)
class LLMFunctionCall:
    """One provider-selected function call with JSON-decoded arguments."""

    call_id: str | None
    name: str
    arguments: dict[str, Any]


async def complete_chat_with_tools(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> LLMFunctionCall:
    """Request exactly one structured function call from an OpenAI-compatible API."""
    config = get_llm_configuration(settings)
    if not tools or len(tools) > 20:
        raise ValueError("Provide between 1 and 20 registered tools.")

    headers = {
        "Authorization": "Bearer " + config.llm_api_key.get_secret_value(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if urlsplit(config.llm_base_url).hostname == "openrouter.ai":
        headers["HTTP-Referer"] = config.openrouter_http_referer
        headers["X-Title"] = config.openrouter_app_title

    try:
        async with httpx.AsyncClient(
            base_url=config.llm_base_url.rstrip("/") + "/",
            headers=headers,
            timeout=httpx.Timeout(config.llm_timeout_seconds),
            transport=transport,
            follow_redirects=False,
        ) as client:
            for attempt in range(config.llm_max_retries + 1):
                response = await client.post(
                    "chat/completions",
                    json={
                        "model": config.llm_model.strip(),
                        "messages": messages,
                        "tools": tools,
                        "tool_choice": "required",
                        "parallel_tool_calls": False,
                        "temperature": 0.1,
                        "max_tokens": min(config.llm_max_completion_tokens, 1200),
                    },
                )
                transient = response.status_code == 429 or response.status_code in {502, 503, 504}
                if not transient or attempt >= config.llm_max_retries:
                    break
                await asyncio.sleep(min(0.25 * (2 ** attempt), 1.0))
    except httpx.TimeoutException as exc:
        raise LLMProviderError("The tool-selection provider timed out. Please retry.") from exc
    except httpx.RequestError as exc:
        raise LLMProviderError("The tool-selection provider could not be reached.") from exc

    if response.status_code == 429:
        raise LLMProviderError("The tool-selection provider rate limit was reached.")
    if response.status_code in {401, 403}:
        raise LLMProviderError("The tool-selection provider rejected the configured credentials.")
    if response.status_code == 402:
        raise LLMProviderError("The tool-selection provider requires account credits or a billing change.")
    if response.status_code >= 500:
        raise LLMProviderError("The tool-selection provider is temporarily unavailable.")
    if not response.is_success:
        raise LLMProviderError(
            f"The tool-selection provider rejected the request (HTTP {response.status_code})."
        )

    try:
        payload = response.json()
        message = payload["choices"][0]["message"]
        calls = message.get("tool_calls")
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise LLMProviderError("The tool-selection provider returned an unexpected response.") from exc

    if not isinstance(calls, list) or len(calls) != 1:
        raise LLMProviderError("The provider must return exactly one registered tool call.")
    call = calls[0]
    if not isinstance(call, dict) or call.get("type") != "function":
        raise LLMProviderError("The provider returned an unsupported tool-call type.")
    function = call.get("function")
    if not isinstance(function, dict):
        raise LLMProviderError("The provider returned an invalid function call.")

    name = function.get("name")
    raw_arguments = function.get("arguments")
    call_id = call.get("id")
    if not isinstance(name, str) or not name or not isinstance(raw_arguments, str):
        raise LLMProviderError("The provider returned incomplete tool-call details.")
    if len(raw_arguments) > 16000:
        raise LLMProviderError("The provider returned tool arguments that exceed the allowed size.")
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise LLMProviderError("The provider returned malformed JSON tool arguments.") from exc
    if not isinstance(arguments, dict):
        raise LLMProviderError("Tool arguments must be a JSON object.")
    if call_id is not None and (not isinstance(call_id, str) or len(call_id) > 128):
        raise LLMProviderError("The provider returned an invalid tool-call identifier.")

    return LLMFunctionCall(call_id=call_id, name=name, arguments=arguments)
