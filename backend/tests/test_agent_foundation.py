"""Tests for Phase 1 agent schemas and deterministic planning policies."""

import pytest
from pydantic import ValidationError

from app.agents.planner import AgentPlanningError, validate_plan
from app.agents.schemas import AgentGoalRequest, AgentPlanProposal


def proposal_payload():
    return {
        "summary": "Inspect the authentication implementation and summarize its flow.",
        "steps": [
            {
                "step_key": "inspect_auth",
                "title": "Inspect authentication code",
                "description": "Review authentication routes and their supporting service functions.",
                "rationale": "These files define the application's authentication boundaries.",
                "expected_output": "A concise map of authentication entry points and checks.",
                "depends_on": [],
                "suggested_tool": "search_code",
            },
            {
                "step_key": "summarize",
                "title": "Summarize authentication behavior",
                "description": "Summarize the observed authentication flow and cite relevant source files.",
                "rationale": "The summary should be grounded in files found during inspection.",
                "expected_output": "A source-grounded authentication overview.",
                "depends_on": ["inspect_auth"],
                "suggested_tool": "draft_report",
            },
        ],
        "completion_criteria": ["Authentication entry points are identified.", "Findings include source evidence."],
        "assumptions": [],
    }


def test_goal_request_validates_limits_and_goal():
    request = AgentGoalRequest(repository_id="4c9f2b10-0000-4000-8000-000000000001", goal="Review authentication")
    assert request.max_steps == 8


def test_goal_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        AgentGoalRequest(
            repository_id="4c9f2b10-0000-4000-8000-000000000001",
            goal="Review authentication safely",
            run_shell=True,
        )


def test_plan_schema_accepts_ordered_dependencies():
    proposal = AgentPlanProposal.model_validate(proposal_payload())
    assert proposal.steps[1].depends_on == ["inspect_auth"]


def test_plan_schema_rejects_duplicate_step_keys():
    payload = proposal_payload()
    payload["steps"][1]["step_key"] = payload["steps"][0]["step_key"]
    with pytest.raises(ValidationError):
        AgentPlanProposal.model_validate(payload)


def test_plan_schema_rejects_forward_dependencies():
    payload = proposal_payload()
    payload["steps"][0]["depends_on"] = ["summarize"]
    with pytest.raises(ValidationError):
        AgentPlanProposal.model_validate(payload)


def test_planner_policy_rejects_excess_steps():
    proposal = AgentPlanProposal.model_validate(proposal_payload())
    with pytest.raises(AgentPlanningError):
        validate_plan(proposal, max_steps=1)


def test_planner_policy_rejects_unregistered_tools():
    payload = proposal_payload()
    payload["steps"][0]["suggested_tool"] = "execute_shell"
    proposal = AgentPlanProposal.model_validate(payload)
    with pytest.raises(AgentPlanningError):
        validate_plan(proposal, max_steps=8)
