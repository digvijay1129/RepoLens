import math

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    OpenAICompatibleEmbeddingProvider,
    get_embedding_configuration,
)


def configured_settings(**overrides) -> Settings:
    base = {
        "environment": "test",
        "embeddings_enabled": True,
        "embeddings_provider": "openai_compatible",
        "embeddings_api_key": SecretStr("local-test-embedding-key"),
        "embeddings_base_url": "https://embedding.example.test/v1",
        "embeddings_model": "tiny-test-model",
        "embeddings_dimensions": 3,
        "embeddings_batch_size": 4,
        "embeddings_timeout_seconds": 5,
    }
    base.update(overrides)
    return Settings(**base)


def test_embeddings_are_opt_in_and_require_nonblank_secret() -> None:
    with pytest.raises(EmbeddingConfigurationError, match="EMBEDDINGS_ENABLED"):
        get_embedding_configuration(Settings(embeddings_enabled=False))

    with pytest.raises(EmbeddingConfigurationError, match="EMBEDDINGS_API_KEY"):
        get_embedding_configuration(configured_settings(embeddings_api_key=SecretStr("")))


def test_provider_rejects_insecure_remote_urls_and_unknown_providers() -> None:
    with pytest.raises(EmbeddingConfigurationError, match="HTTPS"):
        get_embedding_configuration(
            configured_settings(embeddings_base_url="http://embedding.example.test/v1")
        )

    with pytest.raises(EmbeddingConfigurationError, match="Unsupported embedding provider"):
        get_embedding_configuration(configured_settings(embeddings_provider="unknown"))


@pytest.mark.asyncio
async def test_provider_sorts_reversed_response_by_index_and_validates_vectors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "embedding.example.test"
        assert request.url.path == "/v1/embeddings"
        assert request.headers["Authorization"] == "Bearer local-test-embedding-key"
        body = __import__("json").loads(request.content)
        assert body["model"] == "tiny-test-model"
        assert body["dimensions"] == 3
        assert body["input"] == ["first code chunk", "second code chunk"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [4, 5, 6]},
                    {"index": 0, "embedding": [1, 2, 3]},
                ]
            },
            request=request,
        )

    provider = OpenAICompatibleEmbeddingProvider(
        configured_settings(), transport=httpx.MockTransport(handler)
    )
    async with provider:
        vectors = await provider.embed_texts(["first code chunk", "second code chunk"])

    assert vectors == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    assert all(math.isfinite(value) for vector in vectors for value in vector)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, texts, expected_message",
    [
        ({"data": [{"index": 0, "embedding": [1, 2]}]}, ["text"], "unexpected dimension"),
        ({"data": [{"index": 0, "embedding": [float("inf"), 2, 3]}]}, ["text"], "non-finite"),
        (
            {"data": [{"index": 0, "embedding": [1, 2, 3]}, {"index": 0, "embedding": [3, 2, 1]}]},
            ["first", "second"],
            "duplicate",
        ),
    ],
)
async def test_provider_rejects_invalid_provider_responses(payload, texts, expected_message) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    provider = OpenAICompatibleEmbeddingProvider(
        configured_settings(), transport=httpx.MockTransport(handler)
    )
    async with provider:
        with pytest.raises(EmbeddingProviderError, match=expected_message):
            await provider.embed_texts(texts)


@pytest.mark.asyncio
async def test_provider_returns_safe_errors_for_rate_limits_and_auth_failures() -> None:
    for status_code, expected in [
        (429, "rate limit"),
        (401, "rejected the configured credentials"),
        (503, "temporarily unavailable"),
    ]:
        def handler(request: httpx.Request, code=status_code) -> httpx.Response:
            return httpx.Response(code, text="internal provider response should not leak", request=request)

        provider = OpenAICompatibleEmbeddingProvider(
            configured_settings(), transport=httpx.MockTransport(handler)
        )
        async with provider:
            with pytest.raises(EmbeddingProviderError, match=expected) as error:
                await provider.embed_texts(["source text"])
        assert "internal provider response" not in str(error.value)
