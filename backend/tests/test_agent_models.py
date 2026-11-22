"""Database metadata tests for the agent task planning foundation."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base


def test_agent_tables_are_registered():
    assert {"agent_tasks", "agent_plans", "agent_steps", "agent_tool_executions"} <= set(Base.metadata.tables)


def test_agent_metadata_creates_on_sqlite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1
    engine.dispose()


def test_agent_composite_owner_constraints_are_registered():
    task_constraints = {
        item.name for item in Base.metadata.tables["agent_tasks"].constraints
    }
    plan_constraints = {
        item.name for item in Base.metadata.tables["agent_plans"].constraints
    }
    step_constraints = {
        item.name for item in Base.metadata.tables["agent_steps"].constraints
    }
    assert "uq_agent_tasks_id_user_repository" in task_constraints
    assert "uq_agent_plans_id_task_user" in plan_constraints
    assert "fk_agent_steps_plan_owner" in step_constraints


def test_agent_tool_execution_table_is_registered():
    assert {
        "task_id", "step_id", "user_id", "repository_id",
        "tool_name", "status", "tool_input", "tool_output",
    } <= set(Base.metadata.tables["agent_tool_executions"].columns.keys())
