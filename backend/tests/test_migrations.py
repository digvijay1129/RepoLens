"""Ensure Alembic revision metadata matches the application's declared tables."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.base import Base
import app.models  # noqa: F401 -- register models for metadata assertions


def test_alembic_has_a_single_initial_revision() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())

    assert len(revisions) == 1
    assert revisions[0].revision == "20261025_0001"
    assert revisions[0].down_revision is None


def test_model_metadata_has_expected_tables() -> None:
    assert set(Base.metadata.tables) == {"users", "repositories", "indexing_jobs"}
