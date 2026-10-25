"""Tests for safe configuration and errors from the OpenAI-compatible chat client."""

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services.llm import (
    LLMConfigurationError,
    LLMProviderError,
    complete_chat,
    get_llm_configuration,
)


def configured_settings(**overrides) -> Settings:
    data = {
        "environment": "test",
        "llm_enabled": True,
        "llm_provider": "openai_compatible",
        "llm_api_key": SecretStr("private-test-key"),
        "llm_base_url": "https://llm.example.test/v1",
        "llm_model": "small-test-model",
        "llm_timeout_seconds": 5,
        "llm_max_completion_tokens": 256,
    }
    data.update(overrides)
    return Settings(**data)


def test_chat_is_opt_in_and_rejects_missing_secret_and_insecure_remote_urls() -> None:
    with pytest.raises(LLMConfigurationError, match="LLM_ENABLED"):
        get_llm_configuration(Settings(llm_enabled=False))
    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY"):
        get_llm_configuration(configured_settings(llm_api_key=SecretStr("")))
    with pytest.raises(LLMConfigurationError, match="HTTPS"):
        get_llm_configuration(configured_settings(llm_base_url="http://llm.example.test/v1"))


@pytest.mark.asyncio
async def test_chat_completion_posts_system_prompt_and_returns_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer private-test-key"
        body = __import__("json").loads(request.content)
        assert body["model"] == "small-test-model"
        assert body["max_tokens"] == 256
        assert body["messages"][0] == {"role": "system", "content": "grounded instructions"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Authentication is validated in [S1]."}}]},
            request=request,
        )

    answer = await complete_chat(
        [{"role": "system", "content": "grounded instructions"}],
        settings=configured_settings(),
        transport=httpx.MockTransport(handler),
    )
    assert answer == "Authentication is validated in [S1]."


@pytest.mark.asyncio
async def test_chat_provider_errors_do_not_expose_response_body_or_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="private-test-key internal upstream response", request=request)

    with pytest.raises(LLMProviderError, match="rejected the configured credentials") as error:
        await complete_chat(
            [{"role": "system", "content": "test"}],
            settings=configured_settings(),
            transport=httpx.MockTransport(handler),
        )
    assert "private-test-key" not in str(error.value)
    assert "internal upstream response" not in str(error.value)


@pytest.mark.asyncio
async def test_openrouter_settings_override_legacy_chat_config_and_send_optional_headers() -> None:
    settings = configured_settings(
        openrouter_api_key=SecretStr("sk-or-test"),
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_chat_model="openai/gpt-5.6-luna",
        openrouter_http_referer="http://localhost:5173",
        openrouter_app_title="RepoLens Test",
        llm_max_retries=0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "openrouter.ai"
        assert request.url.path == "/api/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer sk-or-test"
        assert request.headers["HTTP-Referer"] == "http://localhost:5173"
        assert request.headers["X-Title"] == "RepoLens Test"
        body = __import__("json").loads(request.content)
        assert body["model"] == "openai/gpt-5.6-luna"
        return httpx.Response(200, json={"choices": [{"message": {"content": "Grounded response [S1]."}}]}, request=request)

    answer = await complete_chat(
        [{"role": "system", "content": "safe prompt"}],
        settings=settings,
        transport=httpx.MockTransport(handler),
    )
    assert answer == "Grounded response [S1]."


@pytest.mark.asyncio
async def test_chat_retries_rate_limit_once_and_succeeds() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, text="retry later", request=request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Recovered [S1]."}}]}, request=request)

    answer = await complete_chat(
        [{"role": "system", "content": "safe prompt"}],
        settings=configured_settings(llm_max_retries=1),
        transport=httpx.MockTransport(handler),
    )
    assert answer == "Recovered [S1]."
    assert calls["count"] == 2
