"""Configurable OpenAI-compatible embedding provider with strict response validation."""

from __future__ import annotations

import math
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from app.core.config import Settings, get_settings


class EmbeddingConfigurationError(RuntimeError):
    """Raised when embedding generation is not configured safely."""


class EmbeddingProviderError(RuntimeError):
    """Raised when the configured provider returns unusable embeddings."""


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimensions: int

    async def __aenter__(self) -> "EmbeddingProvider": ...
    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None: ...
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


def get_embedding_configuration(settings: Settings | None = None) -> Settings:
    """Validate opt-in and required credentials without revealing secret values."""
    settings = settings or get_settings()
    if (
        settings.openrouter_api_key is not None
        and settings.openrouter_api_key.get_secret_value().strip()
    ):
        settings = settings.model_copy(update={
            "embeddings_api_key": settings.openrouter_api_key,
            "embeddings_base_url": settings.openrouter_base_url,
            "embeddings_model": settings.openrouter_embedding_model,
        })
    if not settings.embeddings_enabled:
        raise EmbeddingConfigurationError(
            "Embeddings are disabled. Set EMBEDDINGS_ENABLED=true in backend/.env."
        )
    if (
        settings.embeddings_api_key is None
        or not settings.embeddings_api_key.get_secret_value().strip()
    ):
        raise EmbeddingConfigurationError(
            "The embedding provider is not configured. Set OPENROUTER_API_KEY or the legacy EMBEDDINGS_API_KEY in backend/.env."
        )
    if settings.embeddings_provider.strip().lower() != "openai_compatible":
        raise EmbeddingConfigurationError(
            "Unsupported embedding provider. Use EMBEDDINGS_PROVIDER=openai_compatible."
        )
    if not settings.embeddings_model.strip() or len(settings.embeddings_model) > 150:
        raise EmbeddingConfigurationError("EMBEDDINGS_MODEL must be a non-empty model name.")

    parsed = urlsplit(settings.embeddings_base_url)
    is_local_development = (
        settings.environment.strip().lower() != "production"
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    )
    if parsed.scheme != "https" and not (is_local_development and parsed.scheme == "http"):
        raise EmbeddingConfigurationError(
            "EMBEDDINGS_BASE_URL must use HTTPS (HTTP is allowed for local development only)."
        )
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise EmbeddingConfigurationError("EMBEDDINGS_BASE_URL is invalid.")
    if not 1 <= settings.embeddings_dimensions <= 8192:
        raise EmbeddingConfigurationError("EMBEDDINGS_DIMENSIONS must be between 1 and 8192.")
    if not 1 <= settings.embeddings_batch_size <= 64:
        raise EmbeddingConfigurationError("EMBEDDINGS_BATCH_SIZE must be between 1 and 64.")
    return settings


class OpenAICompatibleEmbeddingProvider:
    """Minimal embeddings client compatible with the OpenAI /embeddings contract."""

    provider_name = "openai_compatible"

    def __init__(self, settings: Settings | None = None, *, transport: Any = None) -> None:
        self.settings = get_embedding_configuration(settings)
        self.model_name = self.settings.embeddings_model.strip()
        self.dimensions = self.settings.embeddings_dimensions
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OpenAICompatibleEmbeddingProvider":
        secret = self.settings.embeddings_api_key
        assert secret is not None  # Enforced by get_embedding_configuration.
        headers = {
            "Authorization": "Bearer " + secret.get_secret_value(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if urlsplit(self.settings.embeddings_base_url).hostname == "openrouter.ai":
            headers["HTTP-Referer"] = self.settings.openrouter_http_referer
            headers["X-Title"] = self.settings.openrouter_app_title
        self._client = httpx.AsyncClient(
            base_url=self.settings.embeddings_base_url.rstrip("/") + "/",
            headers=headers,
            timeout=httpx.Timeout(self.settings.embeddings_timeout_seconds),
            transport=self._transport,
            follow_redirects=False,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed 1–64 text inputs and validate indexes, dimensions and finite values."""
        if not texts or len(texts) > self.settings.embeddings_batch_size:
            raise ValueError(
                f"Embedding requests must contain 1 to {self.settings.embeddings_batch_size} texts."
            )
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding input cannot contain empty text.")
        if self._client is None:
            raise RuntimeError("Embedding provider must be entered before use.")

        try:
            response = await self._client.post(
                "embeddings",
                json={
                    "model": self.model_name,
                    "input": texts,
                    "dimensions": self.dimensions,
                },
            )
        except httpx.TimeoutException as exc:
            raise EmbeddingProviderError(
                "The embedding provider timed out. Retry the embedding job."
            ) from exc
        except httpx.RequestError as exc:
            raise EmbeddingProviderError(
                "The embedding provider could not be reached. Check its configured endpoint."
            ) from exc

        if response.status_code == 429:
            raise EmbeddingProviderError(
                "The embedding provider rate limit was reached. Retry the embedding job later."
            )
        if response.status_code in {401, 403}:
            raise EmbeddingProviderError(
                "The embedding provider rejected the configured credentials."
            )
        if response.status_code == 402:
            raise EmbeddingProviderError(
                "The embedding provider requires account credits or a billing change."
            )
        if response.status_code >= 500:
            raise EmbeddingProviderError(
                "The embedding provider is temporarily unavailable. Retry the embedding job."
            )
        if not response.is_success:
            raise EmbeddingProviderError(
                f"The embedding provider rejected the request (HTTP {response.status_code}). "
                "Check the configured model and dimensions."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise EmbeddingProviderError("The embedding provider returned invalid JSON.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise EmbeddingProviderError("The embedding provider returned an unexpected response.")

        data = payload["data"]
        if len(data) != len(texts):
            raise EmbeddingProviderError("The embedding provider returned an incomplete batch.")

        indexed: dict[int, list[float]] = {}
        for item in data:
            if not isinstance(item, dict) or not isinstance(item.get("index"), int):
                raise EmbeddingProviderError("The embedding provider returned invalid item indexes.")
            index = item["index"]
            raw_vector = item.get("embedding")
            if index < 0 or index >= len(texts) or index in indexed:
                raise EmbeddingProviderError("The embedding provider returned duplicate or invalid indexes.")
            if not isinstance(raw_vector, list) or len(raw_vector) != self.dimensions:
                raise EmbeddingProviderError(
                    f"The embedding provider returned a vector with an unexpected dimension; "
                    f"expected {self.dimensions}."
                )
            vector: list[float] = []
            for value in raw_vector:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise EmbeddingProviderError("The embedding provider returned non-numeric vector values.")
                numeric = float(value)
                if not math.isfinite(numeric):
                    raise EmbeddingProviderError("The embedding provider returned non-finite vector values.")
                vector.append(numeric)
            indexed[index] = vector

        if set(indexed) != set(range(len(texts))):
            raise EmbeddingProviderError("The embedding provider returned an incomplete batch.")
        return [indexed[index] for index in range(len(texts))]
