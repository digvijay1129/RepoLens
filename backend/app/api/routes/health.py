"""Health endpoints for local development and hosting probes."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.session import check_database_connection

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/live", summary="Liveness probe")
def live() -> dict[str, str]:
    """Report that the API process is running without checking dependencies."""
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Readiness probe",
    responses={503: {"description": "Required database dependency is unavailable"}},
)
def ready():
    """Report readiness only when the PostgreSQL connection responds."""
    try:
        check_database_connection()
    except Exception as exc:
        # Keep exception details in service logs, never return connection strings to clients.
        logger.warning("Database readiness check failed (%s).", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "dependency": "database"},
        )
    return {"status": "ready", "database": "ok"}
