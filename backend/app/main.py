"""RepoLens FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="RepoLens combines pgvector retrieval with source-grounded repository chat.",
    version="0.7.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["Service"], summary="Service information")
def service_info() -> dict[str, str]:
    """Expose a small service discovery response without leaking configuration."""
    return {
        "service": "RepoLens API",
        "version": app.version,
        "docs": "/docs",
        "health": settings.api_v1_prefix + "/health/live",
    }
