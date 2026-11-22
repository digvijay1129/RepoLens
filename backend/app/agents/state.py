"""Explicit task-state transition rules shared by agent orchestration services."""

from dataclasses import dataclass, field
from uuid import UUID

from app.agents.schemas import AgentTaskStatus


class InvalidAgentStateTransition(ValueError):
    """Raised when a task attempts a transition that is not allowed."""


_ALLOWED_TRANSITIONS: dict[AgentTaskStatus, set[AgentTaskStatus]] = {
    AgentTaskStatus.QUEUED: {AgentTaskStatus.PLANNING, AgentTaskStatus.CANCELLED},
    AgentTaskStatus.PLANNING: {
        AgentTaskStatus.PLANNED,
        AgentTaskStatus.FAILED,
        AgentTaskStatus.PAUSED,
        AgentTaskStatus.CANCELLED,
    },
    AgentTaskStatus.PLANNED: {AgentTaskStatus.RUNNING, AgentTaskStatus.CANCELLED},
    AgentTaskStatus.PAUSED: {AgentTaskStatus.RUNNING, AgentTaskStatus.CANCELLED},
    AgentTaskStatus.RUNNING: {
        AgentTaskStatus.AWAITING_APPROVAL,
        AgentTaskStatus.COMPLETED,
        AgentTaskStatus.FAILED,
        AgentTaskStatus.CANCELLED,
    },
    AgentTaskStatus.AWAITING_APPROVAL: {
        AgentTaskStatus.RUNNING,
        AgentTaskStatus.FAILED,
        AgentTaskStatus.CANCELLED,
    },
    AgentTaskStatus.COMPLETED: set(),
    AgentTaskStatus.FAILED: set(),
    AgentTaskStatus.CANCELLED: set(),
}


@dataclass
class AgentExecutionState:
    """In-memory representation of durable task state.

    Durable task and step progress is persisted by the execution service. Paused
    tasks can resume from their last successful step without repeating its tool call.
    """

    task_id: UUID
    user_id: UUID
    repository_id: UUID
    indexed_commit_sha: str
    status: AgentTaskStatus = AgentTaskStatus.QUEUED
    current_step_key: str | None = None
    completed_step_keys: list[str] = field(default_factory=list)

    def transition_to(self, next_status: AgentTaskStatus) -> None:
        """Validate and apply one allowed lifecycle transition."""
        if next_status not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidAgentStateTransition(
                f"Cannot transition an agent task from {self.status.value} to {next_status.value}."
            )
        self.status = next_status
        if next_status in {
            AgentTaskStatus.COMPLETED,
            AgentTaskStatus.FAILED,
            AgentTaskStatus.CANCELLED,
        }:
            self.current_step_key = None
