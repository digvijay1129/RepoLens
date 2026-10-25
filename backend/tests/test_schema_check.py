"""Tests for read-only schema verification without needing PostgreSQL."""

import pytest
from sqlalchemy import create_engine, inspect, text

from app.db.base import Base
from app.db.schema_check import expected_alembic_revision, validate_schema
from app.models import IndexingJob, Repository, User  # noqa: F401


@pytest.fixture()
def schema_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE alembic_version "
                "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": expected_alembic_revision()},
        )
    yield engine
    engine.dispose()


def test_schema_validator_accepts_expected_tables_and_constraints(schema_engine) -> None:
    issues = validate_schema(
        inspect(schema_engine),
        applied_revision=expected_alembic_revision(),
        expected_revision=expected_alembic_revision(),
    )
    assert issues == []


def test_schema_validator_reports_revision_mismatch(schema_engine) -> None:
    issues = validate_schema(
        inspect(schema_engine),
        applied_revision="old_revision",
        expected_revision=expected_alembic_revision(),
    )
    assert any("Alembic revision mismatch" in issue for issue in issues)


def test_schema_validator_reports_missing_table() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    issues = validate_schema(
        inspect(engine),
        applied_revision=None,
        expected_revision=expected_alembic_revision(),
    )

    assert any("Missing tables" in issue for issue in issues)
    assert any("Alembic revision mismatch" in issue for issue in issues)
    engine.dispose()


def test_schema_validator_reports_missing_column(schema_engine) -> None:
    real_inspector = inspect(schema_engine)

    class InspectorMissingDisplayName:
        """Delegate to SQLAlchemy Inspector while simulating one missing column."""

        def __getattr__(self, name):
            return getattr(real_inspector, name)

        def get_columns(self, table_name, *args, **kwargs):
            columns = real_inspector.get_columns(table_name, *args, **kwargs)
            if table_name == "users":
                return [column for column in columns if column["name"] != "display_name"]
            return columns

    issues = validate_schema(
        InspectorMissingDisplayName(),
        applied_revision=expected_alembic_revision(),
        expected_revision=expected_alembic_revision(),
    )

    assert any(
        "Table 'users' is missing columns: display_name" in issue
        for issue in issues
    )
