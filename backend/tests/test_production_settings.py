"""Fail-fast production config validation and secure middleware behavior."""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings, validate_production_settings
from app.main import create_app


def safe_production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "jwt_secret_key": SecretStr("a-private-jwt-signing-secret-at-least-32-bytes"),
        "database_url": "postgresql+psycopg://repolens_user:privatepass@db.example.test:5432/repolens?sslmode=verify-full",
        "cors_origins": "https://app.example.com",
        "trusted_hosts": "api.example.com",
        "openrouter_api_key": SecretStr("sk-or-test-only"),
        "openrouter_http_referer": "https://app.example.com",
    }
    values.update(overrides)
    return Settings(**values)


def test_valid_production_configuration_passes() -> None:
    validate_production_settings(safe_production_settings())


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"jwt_secret_key": SecretStr("short")}, "JWT_SECRET_KEY"),
        ({"cors_origins": "*"}, "CORS_ORIGINS"),
        ({"cors_origins": "http://app.example.com"}, "HTTPS"),
        ({"trusted_hosts": "*"}, "TRUSTED_HOSTS"),
        ({"database_url": "postgresql+psycopg://repolens_user:secret@db.example.test:5432/repolens"}, "sslmode"),
        ({"openrouter_http_referer": "http://app.example.com"}, "OPENROUTER_HTTP_REFERER"),
    ],
)
def test_unsafe_production_configuration_is_rejected(overrides, expected: str) -> None:
    with pytest.raises(RuntimeError, match=expected):
        validate_production_settings(safe_production_settings(**overrides))


def test_production_disables_interactive_api_docs_and_sets_security_headers() -> None:
    application = create_app(safe_production_settings())
    client = TestClient(application, base_url="https://api.example.com")

    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["docs"] == "disabled"
    assert root.headers["x-content-type-options"] == "nosniff"
    assert root.headers["x-frame-options"] == "DENY"
    assert root.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_production_trusted_hosts_reject_unrecognized_host_header() -> None:
    application = create_app(safe_production_settings())
    client = TestClient(application, base_url="https://attacker.example")

    response = client.get("/")
    assert response.status_code == 400
