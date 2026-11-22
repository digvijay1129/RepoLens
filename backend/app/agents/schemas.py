"""Validated schemas for agent goals and execution plans."""

from __future__ import annotations

from enum import Enum
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentTaskStatus(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    PLANNED = "planned"
    RUNNING = "running"
    PAUSED = "paused"
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
    approval_mode: Literal["auto", "approve_each"] = "auto"
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
    max_tool_calls: int = 20
    max_retries_per_step: int = 1
    total_tool_calls: int = 0
    total_retries: int = 0
    final_result: dict | None = None
    execution_started_at: str | None = None
    execution_finished_at: str | None = None


class AgentRunRequest(BaseModel):
    """Strict per-run execution budget and bounded retry configuration."""

    model_config = ConfigDict(extra="forbid")

    max_tool_calls: int | None = Field(default=None, ge=1, le=40)
    max_retries_per_step: int = Field(default=1, ge=0, le=2)
    max_runtime_seconds: int = Field(default=90, ge=5, le=180)


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



class AgentMemoryCreateRequest(BaseModel):
    """A user-curated memory scoped to one saved repository."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    memory_type: Literal["architecture", "convention", "decision", "troubleshooting", "note"]
    title: str = Field(min_length=3, max_length=160)
    content: str = Field(min_length=8, max_length=6000)
    tags: list[str] = Field(default_factory=list, max_length=12)
    importance: int = Field(default=3, ge=1, le=5)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    expires_at: datetime | None = None

    @field_validator("tags")
    @classmethod
    def validate_memory_tags(cls, value: list[str]) -> list[str]:
        tags = [tag.strip().casefold() for tag in value if tag.strip()]
        if any(len(tag) > 48 for tag in tags):
            raise ValueError("Memory tags must contain at most 48 characters.")
        return list(dict.fromkeys(tags))


class AgentMemoryUpdateRequest(BaseModel):
    """Editable user-facing fields; provenance and ownership remain immutable."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    memory_type: Literal["architecture", "convention", "decision", "troubleshooting", "note"] | None = None
    title: str | None = Field(default=None, min_length=3, max_length=160)
    content: str | None = Field(default=None, min_length=8, max_length=6000)
    tags: list[str] | None = Field(default=None, max_length=12)
    importance: int | None = Field(default=None, ge=1, le=5)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    is_active: bool | None = None
    expires_at: datetime | None = None

    @field_validator("tags")
    @classmethod
    def validate_update_memory_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        tags = [tag.strip().casefold() for tag in value if tag.strip()]
        if any(len(tag) > 48 for tag in tags):
            raise ValueError("Memory tags must contain at most 48 characters.")
        return list(dict.fromkeys(tags))


class AgentMemoryResponse(BaseModel):
    id: UUID
    repository_id: UUID
    task_id: UUID | None = None
    source_execution_id: UUID | None = None
    memory_type: str
    origin: str
    title: str
    content: str
    tags: list[str]
    source_refs: list[dict]
    source_commit_sha: str | None = None
    confidence: float
    importance: int
    is_active: bool
    access_count: int
    last_accessed_at: str | None = None
    expires_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    relevance_score: float | None = None
    snapshot_matches: bool | None = None



class AgentApprovalDecisionRequest(BaseModel):
    """One authenticated human decision on a pending proposed tool action."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    comment: str | None = Field(default=None, max_length=1000)


class AgentApprovalResponse(BaseModel):
    id: UUID
    task_id: UUID
    step_id: UUID
    delegation_id: UUID | None = None
    executed_execution_id: UUID | None = None
    approval_mode: str
    tool_name: str
    tool_arguments: dict
    specialist_key: str
    policy_reason: str
    status: Literal["pending", "approved", "denied", "expired", "cancelled", "executed"]
    requested_at: str
    expires_at: str
    decided_at: str | None = None
    decided_by_user_id: UUID | None = None
    decision_comment: str | None = None
