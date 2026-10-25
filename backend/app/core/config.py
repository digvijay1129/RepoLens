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

    # Embeddings are opt-in. Source indexing continues to work when disabled.
    embeddings_enabled: bool = False
    embeddings_provider: str = "openai_compatible"
    embeddings_api_key: SecretStr | None = Field(default=None, repr=False)
    embeddings_base_url: str = "https://api.openai.com/v1"
    embeddings_model: str = "text-embedding-3-small"
    embeddings_dimensions: int = Field(default=1536, ge=1, le=8192)
    embeddings_batch_size: int = Field(default=32, ge=1, le=64)
    embeddings_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)

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
