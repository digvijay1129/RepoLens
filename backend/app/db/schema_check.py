"""CLI and reusable checks for the deployed RepoLens database schema.

Run from backend/ with the configured .env:
    python -m app.db.schema_check

This command is read-only. It verifies the applied Alembic revision, required
columns, and named constraints/indexes without printing the database URL.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import DatabaseConfigurationError, get_engine

EXPECTED_COLUMNS: dict[str, set[str]] = {
    "users": {"id", "email", "password_hash", "display_name", "is_active", "created_at", "updated_at"},
    "repositories": {
        "id",
        "user_id",
        "github_repository_id",
        "github_owner",
        "github_name",
        "full_name",
        "canonical_url",
        "description",
        "language",
        "stargazers_count",
        "forks_count",
        "open_issues_count",
        "size",
        "license_name",
        "archived",
        "github_updated_at",
        "default_branch",
        "selected_branch",
        "indexed_commit_sha",
        "indexing_status",
        "last_indexed_at",
        "embedding_status",
        "embedding_provider",
        "embedding_model",
        "embedding_dimensions",
        "last_embedded_at",
        "created_at",
        "updated_at",
    },
    "indexing_jobs": {
        "id",
        "repository_id",
        "user_id",
        "status",
        "job_type",
        "embedding_provider",
        "embedding_model",
        "embedding_dimensions",
        "attempt_count",
        "error_message",
        "total_files",
        "processed_files",
        "skipped_files",
        "chunk_count",
        "commit_sha",
        "progress_message",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    },
    "repository_chunks": {
        "id",
        "repository_id",
        "user_id",
        "commit_sha",
        "file_path",
        "language",
        "chunk_index",
        "start_line",
        "end_line",
        "content_hash",
        "symbol_names",
        "token_count",
        "chunk_text",
        "created_at",
    },
    "repository_chunk_embeddings": {
        "id",
        "chunk_id",
        "repository_id",
        "user_id",
        "commit_sha",
        "provider",
        "model",
        "dimensions",
        "content_hash",
        "vector",
        "created_at",
    },
}

EXPECTED_CONSTRAINTS: dict[str, dict[str, set[str]]] = {
    "users": {
        "primary": {"pk_users"},
        "unique": {"uq_users_email"},
        "check": {"ck_users_email_lowercase"},
        "foreign": set(),
        "indexes": set(),
    },
    "repositories": {
        "primary": {"pk_repositories"},
        "unique": {"uq_repositories_user_full_name", "uq_repositories_id_user_id"},
        "check": {
            "ck_repositories_indexing_status_allowed",
            "ck_repositories_full_name_lowercase",
            "ck_repositories_stargazers_nonnegative",
            "ck_repositories_forks_nonnegative",
            "ck_repositories_open_issues_nonnegative",
            "ck_repositories_embedding_status_allowed",
            "ck_repositories_embedding_dimensions_valid",
        },
        "foreign": {"fk_repositories_user_id_users"},
        "indexes": {"ix_repositories_user_updated"},
    },
    "indexing_jobs": {
        "primary": {"pk_indexing_jobs"},
        "unique": set(),
        "check": {
            "ck_indexing_jobs_status_allowed",
            "ck_indexing_jobs_attempt_count_nonnegative",
            "ck_indexing_jobs_total_files_nonnegative",
            "ck_indexing_jobs_processed_files_nonnegative",
            "ck_indexing_jobs_skipped_files_nonnegative",
            "ck_indexing_jobs_chunk_count_nonnegative",
            "ck_indexing_jobs_job_type_allowed",
        },
        "foreign": {
            "fk_indexing_jobs_user_id_users",
            "fk_indexing_jobs_repository_owner",
        },
        "indexes": {
            "ix_indexing_jobs_user_status_created",
            "ix_indexing_jobs_repository_created",
        },
    },
    "repository_chunks": {
        "primary": {"pk_repository_chunks"},
        "unique": {"uq_repository_chunks_repo_snapshot_file_chunk"},
        "check": {
            "ck_repository_chunks_chunk_index_nonnegative",
            "ck_repository_chunks_start_line_positive",
            "ck_repository_chunks_end_line_valid",
            "ck_repository_chunks_token_count_nonnegative",
        },
        "foreign": {"fk_repository_chunks_repository_owner"},
        "indexes": {
            "ix_repository_chunks_user_repo_commit",
            "ix_repository_chunks_user_repo_path",
        },
    },
    "repository_chunk_embeddings": {
        "primary": {"pk_repository_chunk_embeddings"},
        "unique": {"uq_chunk_embeddings_chunk_provider_model_dimensions"},
        "check": {
            "ck_repository_chunk_embeddings_dimensions_positive",
            "ck_repository_chunk_embeddings_dimensions_maximum",
        },
        "foreign": {
            "fk_repository_chunk_embeddings_chunk_id_repository_chunks",
            "fk_repository_chunk_embeddings_repository_owner",
        },
        "indexes": {"ix_chunk_embeddings_user_repo_commit_model"},
    },
}


def expected_alembic_revision() -> str:
    """Return the repository's current Alembic head revision."""
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    return ScriptDirectory.from_config(config).get_current_head()


def validate_schema(
    schema_inspector: Any,
    applied_revision: str | None,
    expected_revision: str,
) -> list[str]:
    """Return human-readable schema defects, or an empty list when valid."""
    issues: list[str] = []
    table_names = set(schema_inspector.get_table_names())

    missing_tables = set(EXPECTED_COLUMNS) - table_names
    if missing_tables:
        issues.append("Missing tables: " + ", ".join(sorted(missing_tables)))

    for table, expected_columns in EXPECTED_COLUMNS.items():
        if table not in table_names:
            continue
        actual_columns = {
            column["name"] for column in schema_inspector.get_columns(table)
        }
        missing_columns = expected_columns - actual_columns
        if missing_columns:
            issues.append(
                f"Table '{table}' is missing columns: "
                + ", ".join(sorted(missing_columns))
            )

        actual_primary = schema_inspector.get_pk_constraint(table).get("name")
        actual_unique = {
            item.get("name") for item in schema_inspector.get_unique_constraints(table)
        }
        actual_checks = {
            item.get("name") for item in schema_inspector.get_check_constraints(table)
        }
        actual_foreign = {
            item.get("name") for item in schema_inspector.get_foreign_keys(table)
        }
        actual_indexes = {
            item.get("name") for item in schema_inspector.get_indexes(table)
        }

        expected = EXPECTED_CONSTRAINTS[table]
        if expected["primary"] - {actual_primary}:
            issues.append(
                f"Table '{table}' is missing primary key constraint(s): "
                + ", ".join(sorted(expected["primary"] - {actual_primary}))
            )

        for label, actual in (
            ("unique constraint", actual_unique),
            ("check constraint", actual_checks),
            ("foreign key", actual_foreign),
            ("index", actual_indexes),
        ):
            missing = expected[
                {"unique constraint": "unique", "check constraint": "check",
                 "foreign key": "foreign", "index": "indexes"}[label]
            ] - actual
            if missing:
                present_names = ", ".join(
                    sorted(str(name) for name in actual if name)
                ) or "none"
                issues.append(
                    f"Table '{table}' is missing {label}(s): "
                    + ", ".join(sorted(missing))
                    + f" (found: {present_names})"
                )

    dialect = getattr(getattr(schema_inspector, "bind", None), "dialect", None)
    if getattr(dialect, "name", None) == "postgresql" and "repository_chunk_embeddings" in table_names:
        embedding_columns = {
            column["name"]: column for column in schema_inspector.get_columns("repository_chunk_embeddings")
        }
        vector_column = embedding_columns.get("vector")
        if vector_column is not None and "vector" not in str(vector_column["type"]).lower():
            issues.append(
                "Table 'repository_chunk_embeddings' must use the native PostgreSQL vector type."
            )
        chunk_indexes = {
            item.get("name") for item in schema_inspector.get_indexes("repository_chunks")
        }
        if "ix_repository_chunks_fts_simple" not in chunk_indexes:
            issues.append(
                "Table 'repository_chunks' is missing PostgreSQL full-text index "
                "ix_repository_chunks_fts_simple."
            )

    if applied_revision != expected_revision:
        issues.append(
            "Alembic revision mismatch: "
            f"database has {applied_revision or 'no revision'}, "
            f"code expects {expected_revision}."
        )
    return issues


def inspect_database(engine: Engine) -> tuple[str | None, list[str]]:
    """Inspect the live database and return its migration revision and issues."""
    with engine.connect() as connection:
        inspector = inspect(connection)
        applied_revision: str | None = None
        if inspector.has_table("alembic_version"):
            applied_revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()

        issues = validate_schema(
            inspector,
            applied_revision=applied_revision,
            expected_revision=expected_alembic_revision(),
        )
        return applied_revision, issues


def main() -> int:
    """Run the read-only schema check command."""
    try:
        engine = get_engine()
    except DatabaseConfigurationError as exc:
        print(f"Database configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        applied_revision, issues = inspect_database(engine)
    except SQLAlchemyError as exc:
        # Avoid printing SQLAlchemy's raw exception text, which can contain the
        # database host or other connection details.
        print(
            "Unable to inspect PostgreSQL ("
            f"{type(exc).__name__}). Verify DATABASE_URL and that PostgreSQL is running.",
            file=sys.stderr,
        )
        return 2
    finally:
        engine.dispose()

    if issues:
        print("RepoLens database schema check failed:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print(
        "RepoLens database schema check passed "
        f"(Alembic revision {applied_revision}; "
        f"{len(EXPECTED_COLUMNS)} application tables verified)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
