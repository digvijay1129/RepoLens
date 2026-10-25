"""Database URL configuration tests without opening a connection."""

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.db import session as db_session


def test_database_url_is_required(monkeypatch) -> None:
    monkeypatch.setattr(db_session, "get_settings", lambda: SimpleNamespace(database_url=None))

    with pytest.raises(db_session.DatabaseConfigurationError, match="DATABASE_URL is not configured"):
        db_session.get_database_url()


def test_generic_postgresql_url_is_normalized_to_psycopg_three(monkeypatch) -> None:
    monkeypatch.setattr(
        db_session,
        "get_settings",
        lambda: SimpleNamespace(database_url="postgresql://repolens:localpass@localhost:5432/repolens"),
    )

    value = db_session.get_database_url()

    assert value.startswith("postgresql+psycopg://")
    assert "localhost:5432/repolens" in value


def test_unsupported_database_driver_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        db_session,
        "get_settings",
        lambda: SimpleNamespace(database_url="sqlite:///repolens.db"),
    )

    with pytest.raises(db_session.DatabaseConfigurationError, match="requires PostgreSQL"):
        db_session.get_database_url()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://",
        "postgresql+psycopg://localhost",
        "postgresql+psycopg:///repolens",
    ],
)
def test_database_url_requires_database_and_username(monkeypatch, url: str) -> None:
    monkeypatch.setattr(
        db_session,
        "get_settings",
        lambda: SimpleNamespace(database_url=url),
    )

    with pytest.raises(
        db_session.DatabaseConfigurationError,
        match="database name and username",
    ):
        db_session.get_database_url()


def test_password_is_excluded_from_settings_repr() -> None:
    settings = Settings(
        app_name="RepoLens API",
        database_url="postgresql+psycopg://repolens:private-value@localhost/repolens",
    )

    assert "private-value" not in repr(settings)
    assert "database_url" not in repr(settings)
