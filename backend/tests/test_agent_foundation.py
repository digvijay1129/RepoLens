"""Tests for Phase 1 agent schemas and deterministic planning policies."""

import json

import pytest
from pydantic import SecretStr, ValidationError

from app.agents.planner import AgentPlanningError, create_plan, validate_plan
from app.agents.schemas import AgentGoalRequest, AgentPlanProposal
from app.core.config import Settings


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
                "suggested_tool": "repository_overview",
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



@pytest.mark.asyncio
async def test_planner_uses_existing_llm_client_and_returns_structured_plan():
    settings = Settings(
        llm_enabled=True,
        llm_api_key=SecretStr("unit-test-secret"),
        llm_base_url="https://provider.example/v1",
        llm_model="unit-test-planner",
    )
    captured = {}

    async def fake_completion(messages, *, settings):
        captured["messages"] = messages
        captured["model"] = settings.llm_model
        return json.dumps(proposal_payload())

    proposal, effective_settings = await create_plan(
        "Review the authentication architecture and summarize the flow.",
        max_steps=4,
        settings_factory=lambda: settings,
        completion_func=fake_completion,
    )

    assert len(proposal.steps) == 2
    assert effective_settings.llm_model == "unit-test-planner"
    assert captured["model"] == "unit-test-planner"
    assert "Return one JSON object" in captured["messages"][1]["content"]


@pytest.mark.asyncio
async def test_planner_uses_openrouter_override_for_model_metadata():
    settings = Settings(
        llm_enabled=True,
        openrouter_api_key=SecretStr("unit-test-openrouter-secret"),
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_chat_model="provider/agent-planner-test",
    )

    async def fake_completion(messages, *, settings):
        assert settings.llm_model == "provider/agent-planner-test"
        return json.dumps(proposal_payload())

    _, effective_settings = await create_plan(
        "Inspect repository dependencies and explain the architecture.",
        max_steps=5,
        settings_factory=lambda: settings,
        completion_func=fake_completion,
    )

    assert effective_settings.llm_model == "provider/agent-planner-test"


@pytest.mark.asyncio
async def test_planner_rejects_non_json_provider_output():
    settings = Settings(
        llm_enabled=True,
        llm_api_key=SecretStr("unit-test-secret"),
        llm_base_url="https://provider.example/v1",
        llm_model="unit-test-planner",
    )

    async def fake_completion(messages, *, settings):
        return "Here is your plan: run a shell command"

    with pytest.raises(AgentPlanningError):
        await create_plan(
            "Investigate this repository for potential bugs.",
            max_steps=4,
            settings_factory=lambda: settings,
            completion_func=fake_completion,
        )


def test_agent_api_routes_are_registered_in_openapi():
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/agents/tasks" in paths
    assert {"get", "post"} <= set(paths["/api/v1/agents/tasks"])
    assert "/api/v1/agents/tasks/{task_id}" in paths
    assert "get" in paths["/api/v1/agents/tasks/{task_id}"]
    assert "/api/v1/agents/tasks/{task_id}/cancel" in paths
    assert "post" in paths["/api/v1/agents/tasks/{task_id}/cancel"]
    assert "/api/v1/agents/repositories/{repository_id}/memories" in paths
    assert {"get", "post"} <= set(
        paths["/api/v1/agents/repositories/{repository_id}/memories"]
    )
    assert "/api/v1/agents/memories/{memory_id}" in paths
    assert {"patch", "delete"} <= set(paths["/api/v1/agents/memories/{memory_id}"])
    assert "/api/v1/agents/tasks/{task_id}/team" in paths
    assert "get" in paths["/api/v1/agents/tasks/{task_id}/team"]
    assert "/api/v1/agents/tasks/{task_id}/delegations" in paths
    assert "get" in paths["/api/v1/agents/tasks/{task_id}/delegations"]



def test_specialist_router_assigns_all_fixed_roles_deterministically():
    from types import SimpleNamespace

    from app.agents.team import route_step_to_specialist

    cases = [
        ("Find authentication entry points", "Identify relevant modules and file locations.", "research"),
        ("Review token validation", "Analyze the authentication control flow and security checks.", "code_analysis"),
        ("Map system architecture", "Document component boundaries and data flow.", "architecture"),
        ("Debug failing integration test", "Trace the traceback and identify a likely regression.", "debugging"),
        ("Document API usage", "Prepare a developer guide and README reference.", "documentation"),
    ]
    for title, description, expected in cases:
        step = SimpleNamespace(
            title=title,
            description=description,
            rationale="Produce evidence-based findings for the coordinator.",
            expected_output="A concise result with repository citations.",
            suggested_tool="search_code",
        )
        assert route_step_to_specialist(step).key == expected
