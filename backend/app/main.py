"""RepoLens FastAPI application entry point with production-safe defaults."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings, validate_production_settings


def create_app(runtime_settings: Settings | None = None) -> FastAPI:
    """Build an application; production settings are validated before serving traffic."""
    settings = runtime_settings or get_settings()
    is_production = settings.environment.strip().lower() == "production"
    validate_production_settings(settings)

    application = FastAPI(
        title=settings.app_name,
        description="RepoLens combines OpenRouter-compatible RAG chat, retrieval, and offline evaluation.",
        version="0.9.0",
        # The interactive API consoles are useful locally, but broaden the public
        # attack surface and disclose endpoint schemas in a production deployment.
        openapi_url=None if is_production else "/openapi.json",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
    )

    if is_production:
        application.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.trusted_host_list,
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        max_age=600,
    )

    @application.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith(settings.api_v1_prefix):
            # API responses are user-specific, including authenticated repository data.
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    application.include_router(api_router, prefix=settings.api_v1_prefix)

    @application.get("/", tags=["Service"], summary="Service information")
    def service_info() -> dict[str, str]:
        """Expose a small service discovery response without leaking configuration."""
        return {
            "service": "RepoLens API",
            "version": application.version,
            "docs": "/docs" if not is_production else "disabled",
            "health": settings.api_v1_prefix + "/health/live",
        }

    return application


app = create_app()
