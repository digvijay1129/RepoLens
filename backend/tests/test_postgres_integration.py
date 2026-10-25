"""Optional read-only integration checks against a migrated PostgreSQL database.

Set REPOLENS_TEST_DATABASE_URL to a dedicated local/test database URL after
running `alembic upgrade head`. The test never creates, migrates, or deletes
tables. CI provisions a disposable PostgreSQL database and runs it after the
migration step.
"""

import os

import pytest
from sqlalchemy import create_engine, text

from app.db.schema_check import inspect_database

TEST_DATABASE_URL = os.getenv("REPOLENS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set REPOLENS_TEST_DATABASE_URL to run live PostgreSQL integration tests.",
)


def test_migrated_postgres_database_has_expected_schema() -> None:
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
        applied_revision, issues = inspect_database(engine)
        assert applied_revision is not None
        assert issues == []
    finally:
        engine.dispose()
