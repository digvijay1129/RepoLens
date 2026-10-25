"""Environment-backed application settings."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration; secret values are excluded from representations."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "RepoLens API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"
    database_url: str | None = Field(default=None, repr=False)
    jwt_secret_key: SecretStr | None = Field(default=None, repr=False)
    jwt_access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)

    # OpenRouter can use one backend-only key for both chat and embeddings.
    openrouter_api_key: SecretStr | None = Field(default=None, repr=False)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_chat_model: str = "openai/gpt-5.6-luna"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_http_referer: str = "http://localhost:5173"
    openrouter_app_title: str = "RepoLens"

    # Embeddings are opt-in. Source indexing continues to work when disabled.
    embeddings_enabled: bool = False
    embeddings_provider: str = "openai_compatible"
    embeddings_api_key: SecretStr | None = Field(default=None, repr=False)
    embeddings_base_url: str = "https://api.openai.com/v1"
    embeddings_model: str = "text-embedding-3-small"
    embeddings_dimensions: int = Field(default=1536, ge=1, le=8192)
    embeddings_batch_size: int = Field(default=32, ge=1, le=64)
    embeddings_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)

    # Chat generation is separate from embeddings and is opt-in.
    llm_enabled: bool = False
    llm_provider: str = "openai_compatible"
    llm_api_key: SecretStr | None = Field(default=None, repr=False)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = Field(default=60.0, ge=1.0, le=180.0)
    llm_max_completion_tokens: int = Field(default=1200, ge=128, le=4096)
    llm_max_retries: int = Field(default=2, ge=0, le=3)
    rag_context_chunks: int = Field(default=8, ge=1, le=12)
    rag_history_messages: int = Field(default=8, ge=0, le=16)

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a normalized allow-list."""
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for consistent application configuration."""
    return Settings()
