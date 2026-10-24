"""Contract tests for the Phase 1A health endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_service_information() -> None:
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "RepoLens API"
    assert payload["version"] == "0.1.0"


def test_liveness_endpoint_returns_ok() -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_returns_ready() -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_openapi_documents_health_routes() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/health/live" in paths
    assert "/api/v1/health/ready" in paths
