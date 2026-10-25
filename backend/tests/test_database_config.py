"""Database URL configuration tests without opening a connection."""

from types import SimpleNamespace

import pytest

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
