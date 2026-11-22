"""Validated schemas for agent goals and execution plans."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentTaskStatus(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    PLANNED = "planned"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStepStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class AgentGoalRequest(BaseModel):
    """A user-authored goal scoped to one saved repository."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    repository_id: UUID
    goal: str = Field(min_length=8, max_length=4000)
    max_steps: int = Field(default=8, ge=1, le=20)

    @field_validator("goal")
    @classmethod
    def goal_must_be_meaningful(cls, value: str) -> str:
        if len(value.split()) < 2:
            raise ValueError("Goal must contain at least two words.")
        return value


class AgentPlanStepInput(BaseModel):
    """One declarative plan step; it does not execute a tool."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    step_key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,47}$")
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=8, max_length=1200)
    rationale: str = Field(min_length=8, max_length=800)
    expected_output: str = Field(min_length=3, max_length=500)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    suggested_tool: str | None = Field(default=None, max_length=80)


class AgentPlanProposal(BaseModel):
    """Structured planner output validated before persistence."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    summary: str = Field(min_length=10, max_length=1000)
    steps: list[AgentPlanStepInput] = Field(min_length=1, max_length=20)
    completion_criteria: list[str] = Field(min_length=1, max_length=12)
    assumptions: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("steps")
    @classmethod
    def validate_unique_step_keys_and_dependencies(
        cls, steps: list[AgentPlanStepInput]
    ) -> list[AgentPlanStepInput]:
        keys = [step.step_key for step in steps]
        if len(keys) != len(set(keys)):
            raise ValueError("Plan step keys must be unique.")
        seen: set[str] = set()
        for step in steps:
            unknown = set(step.depends_on) - set(keys)
            if unknown:
                raise ValueError(f"Step {step.step_key} has unknown dependencies.")
            if step.step_key in step.depends_on:
                raise ValueError(f"Step {step.step_key} cannot depend on itself.")
            if any(dependency not in seen for dependency in step.depends_on):
                raise ValueError("Plan dependencies must refer to earlier steps.")
            seen.add(step.step_key)
        return steps


class AgentPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=8, max_length=4000)
    max_steps: int = Field(default=8, ge=1, le=20)


class AgentPlanResponse(BaseModel):
    task_id: UUID
    repository_id: UUID
    status: AgentTaskStatus
    summary: str
    steps: list[dict]
    completion_criteria: list[str]
    assumptions: list[str]
    planner_provider: str
    planner_model: str
    created_at: str


class AgentTaskSummary(BaseModel):
    id: UUID
    repository_id: UUID
    goal: str
    status: AgentTaskStatus
    max_steps: int
    created_at: str
    updated_at: str


class AgentTaskDetail(AgentTaskSummary):
    plan: dict | None = None
    steps: list[dict]
    latest_error: str | None = None


class AgentStepExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    instruction: str | None = Field(default=None, max_length=1500)


class AgentToolExecutionResponse(BaseModel):
    id: UUID
    task_id: UUID
    step_id: UUID
    tool_name: str
    status: Literal["running", "succeeded", "failed"]
    tool_input: dict
    tool_output: dict | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    created_at: str
    finished_at: str | None = None
