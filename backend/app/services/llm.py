"""Configurable OpenAI-compatible chat completion client for repository-grounded RAG."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import Settings, get_settings


class LLMConfigurationError(RuntimeError):
    """Raised if an LLM call is disabled or missing safe configuration."""


class LLMProviderError(RuntimeError):
    """Raised when the configured LLM provider cannot return a usable answer."""


def get_llm_configuration(settings: Settings | None = None) -> Settings:
    settings = settings or get_settings()
    if (
        settings.openrouter_api_key is not None
        and settings.openrouter_api_key.get_secret_value().strip()
    ):
        settings = settings.model_copy(update={
            "llm_api_key": settings.openrouter_api_key,
            "llm_base_url": settings.openrouter_base_url,
            "llm_model": settings.openrouter_chat_model,
        })
    if not settings.llm_enabled:
        raise LLMConfigurationError(
            "RAG chat is disabled. Set LLM_ENABLED=true in backend/.env to enable it."
        )
    if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value().strip():
        raise LLMConfigurationError(
            "The chat provider is not configured. Set OPENROUTER_API_KEY or the legacy LLM_API_KEY in backend/.env."
        )
    if settings.llm_provider.strip().lower() != "openai_compatible":
        raise LLMConfigurationError(
            "Unsupported chat provider. Set LLM_PROVIDER=openai_compatible."
        )
    if not settings.llm_model.strip() or len(settings.llm_model) > 150:
        raise LLMConfigurationError("LLM_MODEL must be a non-empty model name.")
    parsed = urlsplit(settings.llm_base_url)
    local_development = (
        settings.environment.strip().lower() != "production"
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    )
    if parsed.scheme != "https" and not (local_development and parsed.scheme == "http"):
        raise LLMConfigurationError(
            "LLM_BASE_URL must use HTTPS (HTTP is allowed for localhost during local development only)."
        )
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise LLMConfigurationError("LLM_BASE_URL is invalid.")
    return settings


async def complete_chat(
    messages: list[dict[str, str]],
    *,
    settings: Settings | None = None,
    transport: Any = None,
) -> str:
    """Send a bounded chat-completion request and return validated plain text."""
    import asyncio

    config = get_llm_configuration(settings)
    client_settings = config
    headers = {
        "Authorization": "Bearer " + client_settings.llm_api_key.get_secret_value(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if urlsplit(client_settings.llm_base_url).hostname == "openrouter.ai":
        headers["HTTP-Referer"] = client_settings.openrouter_http_referer
        headers["X-Title"] = client_settings.openrouter_app_title
    try:
        async with httpx.AsyncClient(
            base_url=client_settings.llm_base_url.rstrip("/") + "/",
            headers=headers,
            timeout=httpx.Timeout(client_settings.llm_timeout_seconds),
            transport=transport,
            follow_redirects=False,
        ) as client:
            for attempt in range(client_settings.llm_max_retries + 1):
                response = await client.post(
                    "chat/completions",
                    json={
                        "model": client_settings.llm_model.strip(),
                        "messages": messages,
                        "temperature": 0.1,
                        "max_tokens": client_settings.llm_max_completion_tokens,
                    },
                )
                transient = response.status_code == 429 or response.status_code in {502, 503, 504}
                if not transient or attempt >= client_settings.llm_max_retries:
                    break
                # Small bounded backoff; never echo response bodies or credentials.
                await asyncio.sleep(min(0.25 * (2 ** attempt), 1.0))
    except httpx.TimeoutException as exc:
        raise LLMProviderError("The chat provider timed out. Please retry your question.") from exc
    except httpx.RequestError as exc:
        raise LLMProviderError(
            "The chat provider could not be reached. Check its configured endpoint."
        ) from exc

    if response.status_code == 429:
        raise LLMProviderError("The chat provider rate limit was reached. Please retry later.")
    if response.status_code in {401, 403}:
        raise LLMProviderError("The chat provider rejected the configured credentials.")
    if response.status_code == 402:
        raise LLMProviderError("The chat provider requires account credits or a billing change.")
    if response.status_code >= 500:
        raise LLMProviderError("The chat provider is temporarily unavailable. Please retry later.")
    if not response.is_success:
        raise LLMProviderError(
            f"The chat provider rejected the request (HTTP {response.status_code}). "
            "Check the configured model and endpoint."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise LLMProviderError("The chat provider returned invalid JSON.") from exc
    try:
        answer = payload["choices"][0]["message"]["content"]
    except (TypeError, KeyError, IndexError) as exc:
        raise LLMProviderError("The chat provider returned an unexpected response.") from exc
    if not isinstance(answer, str) or not answer.strip():
        raise LLMProviderError("The chat provider returned an empty answer.")
    answer = answer.strip()
    if len(answer) > 20000:
        answer = answer[:19970].rstrip() + "\n\n[Answer truncated to the maximum supported length.]"
    return answer
