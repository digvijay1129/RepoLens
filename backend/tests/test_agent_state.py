"""Tests for the explicit agent task lifecycle state machine."""

from uuid import uuid4

import pytest

from app.agents.schemas import AgentTaskStatus
from app.agents.state import AgentExecutionState, InvalidAgentStateTransition


def make_state(status=AgentTaskStatus.QUEUED):
    return AgentExecutionState(
        task_id=uuid4(),
        user_id=uuid4(),
        repository_id=uuid4(),
        indexed_commit_sha="a" * 40,
        status=status,
    )


def test_planning_lifecycle_allows_queued_to_planned():
    state = make_state()
    state.transition_to(AgentTaskStatus.PLANNING)
    state.transition_to(AgentTaskStatus.PLANNED)
    assert state.status is AgentTaskStatus.PLANNED


def test_planned_task_can_be_cancelled():
    state = make_state(AgentTaskStatus.PLANNED)
    state.current_step_key = "inspect_auth"
    state.transition_to(AgentTaskStatus.CANCELLED)
    assert state.status is AgentTaskStatus.CANCELLED
    assert state.current_step_key is None


def test_terminal_state_cannot_be_restarted():
    state = make_state(AgentTaskStatus.COMPLETED)
    with pytest.raises(InvalidAgentStateTransition):
        state.transition_to(AgentTaskStatus.RUNNING)


def test_queued_task_cannot_skip_planning():
    state = make_state()
    with pytest.raises(InvalidAgentStateTransition):
        state.transition_to(AgentTaskStatus.RUNNING)
