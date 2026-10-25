"""Environment-backed application settings and deployment validation."""

from functools import lru_cache
from urllib.parse import urlsplit

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
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
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

    @property
    def trusted_host_list(self) -> list[str]:
        """Parse comma-separated allowed Host header values."""
        return [host.strip().lower() for host in self.trusted_hosts.split(",") if host.strip()]


def validate_production_settings(settings: Settings) -> None:
    """Fail fast when the explicit production environment has unsafe/missing settings.

    This validates deployment configuration, not the security of the hosting platform.
    Values/secrets are never included in exception text.
    """
    if settings.environment.strip().lower() != "production":
        return

    errors: list[str] = []
    secret = settings.jwt_secret_key.get_secret_value() if settings.jwt_secret_key else ""
    if len(secret.encode("utf-8")) < 32:
        errors.append("JWT_SECRET_KEY must contain at least 32 bytes.")

    raw_database_url = (settings.database_url or "").strip()
    parsed_db = urlsplit(raw_database_url)
    if (
        parsed_db.scheme not in {"postgresql", "postgresql+psycopg"}
        or not parsed_db.hostname
        or not parsed_db.username
        or parsed_db.path in {"", "/"}
    ):
        errors.append("DATABASE_URL must identify a PostgreSQL database, username, and host.")
    elif parsed_db.hostname not in {"localhost", "127.0.0.1", "::1"}:
        # Managed databases should use TLS. Require sslmode=require/verify-ca/verify-full.
        from urllib.parse import parse_qs

        sslmode = parse_qs(parsed_db.query).get("sslmode", [""])[0].lower()
        if sslmode not in {"require", "verify-ca", "verify-full"}:
            errors.append("DATABASE_URL for a remote database must set sslmode=require or stronger.")

    origins = settings.cors_origin_list
    if not origins or "*" in origins:
        errors.append("CORS_ORIGINS must list explicit HTTPS frontend origins; wildcard is not allowed.")
    else:
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                errors.append("Every production CORS_ORIGINS entry must be a public HTTPS origin.")
                break

    hosts = settings.trusted_host_list
    if not hosts or "*" in hosts or any(host in {"localhost", "127.0.0.1", "::1", "testserver"} for host in hosts):
        errors.append("TRUSTED_HOSTS must contain explicit production hostnames, not wildcards or local test hosts.")

    if settings.openrouter_api_key and settings.openrouter_api_key.get_secret_value().strip():
        referer = urlsplit(settings.openrouter_http_referer)
        if (
            referer.scheme != "https"
            or not referer.hostname
            or referer.hostname in {"localhost", "127.0.0.1", "::1"}
            or referer.path not in {"", "/"}
            or referer.query
            or referer.fragment
        ):
            errors.append("OPENROUTER_HTTP_REFERER must be a public HTTPS origin in production.")

    if errors:
        joined = " ".join(errors)
        raise RuntimeError("Production configuration is incomplete or unsafe: " + joined)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for consistent application configuration."""
    return Settings()
