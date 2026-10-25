"""Top-level versioned API router."""

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.repositories import router as repositories_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["Health"])
api_router.include_router(repositories_router, prefix="/repositories", tags=["Repositories"])
