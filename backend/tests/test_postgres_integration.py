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


def test_pgvector_cosine_distance_and_postgres_full_text_are_available() -> None:
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            # TEMP objects make this integration smoke test read/write only within
            # the current connection and avoid changing the application's data.
            connection.execute(text("CREATE TEMP TABLE repolens_vector_smoke (id integer, embedding vector)"))
            connection.execute(
                text("INSERT INTO repolens_vector_smoke (id, embedding) VALUES (1, '[1,0,0]'), (2, '[0,1,0]')")
            )
            nearest = connection.execute(
                text("SELECT id FROM repolens_vector_smoke ORDER BY embedding <=> '[1,0,0]'::vector LIMIT 1")
            ).scalar_one()
            keyword_match = connection.execute(
                text("SELECT to_tsvector('simple', 'authenticate_user handler') @@ plainto_tsquery('simple', 'authenticate_user')")
            ).scalar_one()
        assert nearest == 1
        assert keyword_match is True
    finally:
        engine.dispose()
