"""Contract tests for service and database readiness endpoints."""

from fastapi.testclient import TestClient

from app.api.routes import health
from app.main import app

client = TestClient(app)


def test_root_returns_service_information() -> None:
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "RepoLens API"
    assert payload["version"] == "0.9.0"


def test_liveness_endpoint_does_not_require_database(monkeypatch) -> None:
    def unexpected_database_call() -> None:
        raise AssertionError("Liveness must not open database connections.")

    monkeypatch.setattr(health, "check_database_connection", unexpected_database_call)
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_reports_database_available(monkeypatch) -> None:
    monkeypatch.setattr(health, "check_database_connection", lambda: None)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_readiness_endpoint_fails_safely_when_database_is_unavailable(monkeypatch) -> None:
    def unavailable() -> None:
        raise RuntimeError("postgresql://secret-user:super-secret@localhost/private")

    monkeypatch.setattr(health, "check_database_connection", unavailable)
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "dependency": "database"}
    assert "super-secret" not in response.text
    assert "localhost" not in response.text


def test_openapi_documents_health_routes() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/health/live" in paths
    assert "/api/v1/health/ready" in paths



def test_api_responses_include_security_and_no_store_headers() -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["cache-control"] == "no-store"
