"""Ensure the Alembic revision graph is a single linear history."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.base import Base
import app.models  # noqa: F401 -- register models for metadata assertions


def test_alembic_has_a_linear_five_revision_history() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    revisions = {revision.revision: revision for revision in script.walk_revisions()}

    assert set(revisions) == {"20261025_0001", "20261025_0002", "20261025_0003", "20261025_0004", "20261025_0005"}
    assert revisions["20261025_0001"].down_revision is None
    assert revisions["20261025_0002"].down_revision == "20261025_0001"
    assert revisions["20261025_0003"].down_revision == "20261025_0002"
    assert revisions["20261025_0004"].down_revision == "20261025_0003"
    assert revisions["20261025_0005"].down_revision == "20261025_0004"
    assert script.get_current_head() == "20261025_0005"


def test_model_metadata_has_expected_tables() -> None:
    assert set(Base.metadata.tables) == {"users", "repositories", "indexing_jobs", "repository_chunks", "repository_chunk_embeddings"}


def test_models_include_phase_3b_persistence_fields() -> None:
    assert {"password_hash", "is_active"} <= set(Base.metadata.tables["users"].columns.keys())
    assert {
        "github_repository_id", "description", "language", "selected_branch",
        "github_updated_at", "stargazers_count",
    } <= set(Base.metadata.tables["repositories"].columns.keys())
    assert {"total_files", "processed_files", "skipped_files", "chunk_count", "commit_sha"} <= set(
        Base.metadata.tables["indexing_jobs"].columns.keys()
    )
    assert {"file_path", "chunk_text", "content_hash", "symbol_names", "commit_sha", "start_line", "end_line"} <= set(
        Base.metadata.tables["repository_chunks"].columns.keys()
    )
    assert {"embedding_status", "embedding_provider", "embedding_model", "embedding_dimensions", "last_embedded_at"} <= set(
        Base.metadata.tables["repositories"].columns.keys()
    )
    assert {"job_type", "embedding_provider", "embedding_model", "embedding_dimensions"} <= set(
        Base.metadata.tables["indexing_jobs"].columns.keys()
    )
    assert {"provider", "model", "dimensions", "content_hash", "vector"} <= set(
        Base.metadata.tables["repository_chunk_embeddings"].columns.keys()
    )
