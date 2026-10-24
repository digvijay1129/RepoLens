"""Health endpoints for local development and hosting probes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/live", summary="Liveness probe")
def live() -> dict[str, str]:
    """Report that the API process is running without checking dependencies."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
def ready() -> dict[str, str]:
    """Report application readiness.

    Phase 1 has no external runtime dependency. Phase 2 will add a database
    connectivity check before readiness is reported.
    """
    return {"status": "ready"}
