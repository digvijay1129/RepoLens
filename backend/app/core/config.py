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
