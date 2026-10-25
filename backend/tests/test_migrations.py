"""Ensure the Alembic revision graph is a single linear history."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.base import Base
import app.models  # noqa: F401 -- register models for metadata assertions


def test_alembic_has_a_linear_two_revision_history() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    revisions = {revision.revision: revision for revision in script.walk_revisions()}

    assert set(revisions) == {"20261025_0001", "20261025_0002"}
    assert revisions["20261025_0001"].down_revision is None
    assert revisions["20261025_0002"].down_revision == "20261025_0001"
    assert script.get_current_head() == "20261025_0002"


def test_model_metadata_has_expected_tables() -> None:
    assert set(Base.metadata.tables) == {"users", "repositories", "indexing_jobs"}
