"""Database metadata tests for the agent task planning foundation."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base


def test_agent_tables_are_registered():
    assert {"agent_tasks", "agent_plans", "agent_steps"} <= set(Base.metadata.tables)


def test_agent_metadata_creates_on_sqlite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert session.execute("SELECT 1").scalar_one() == 1
    engine.dispose()
