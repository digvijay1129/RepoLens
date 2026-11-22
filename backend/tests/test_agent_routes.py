"""HTTP-level tests for authenticated Phase 1 agent task endpoints."""

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.agents.orchestrator import AgentOrchestrator, AgentPlanningResult
from app.agents.schemas import AgentPlanProposal
from app.services.llm_tools import LLMFunctionCall
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models.repository import Repository
from app.services import auth as auth_service
from app.services.github_client import get_github_client


class FakeGitHubClient:
    async def inspect_repository(self, repository_url: str) -> dict:
        return {
            "id": 741852,
            "name": "RepoLens",
            "full_name": "Digvijay1129/RepoLens",
            "description": "Repository intelligence",
            "html_url": "https://github.com/Digvijay1129/RepoLens",
            "default_branch": "main",
            "language": "Python",
            "stargazers_count": 4,
            "forks_count": 2,
            "open_issues_count": 3,
            "size": 170,
            "updated_at": datetime(2026, 10, 25, tzinfo=timezone.utc).isoformat(),
            "license_name": "MIT License",
            "archived": False,
            "private": False,
        }


@pytest.fixture()
def agent_client(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    def override_db_session():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_github_client] = lambda: FakeGitHubClient()
    test_settings = Settings(
        environment="test",
        jwt_secret_key=SecretStr("repolens-test-signing-secret-32-bytes-minimum"),
        jwt_access_token_expire_minutes=60,
    )
    monkeypatch.setattr(auth_service, "get_settings", lambda: test_settings)

    with TestClient(app) as client:
        app.state.agent_test_engine = engine
        yield client

    app.dependency_overrides.clear()
    engine.dispose()


def create_account(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "a-strong-test-password-2026",
            "display_name": "Agent Test",
        },
    )
    assert response.status_code == 201, response.text
    account = response.json()
    return {
        "headers": {"Authorization": f"Bearer {account['access_token']}"},
        "user": account["user"],
    }


def create_saved_repository(client: TestClient, headers: dict) -> dict:
    response = client.post(
        "/api/v1/repositories/saved",
        headers=headers,
        json={"repository_url": "https://github.com/Digvijay1129/RepoLens"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def mark_repository_indexed(client: TestClient, repository_id: str) -> None:
    with Session(client.app.state.agent_test_engine) as db:
        repository = db.get(Repository, UUID(repository_id))
        repository.indexing_status = "indexed"
        repository.indexed_commit_sha = "a" * 40
        db.commit()


def planned_result() -> AgentPlanningResult:
    proposal = AgentPlanProposal.model_validate(
        {
            "summary": "Inspect the authentication implementation and explain its trust boundaries.",
            "steps": [
                {
                    "step_key": "find_auth",
                    "title": "Find authentication entry points",
                    "description": "Identify authentication routes and the token validation service.",
                    "rationale": "The routes and service define how workspace identity is established.",
                    "expected_output": "A list of authentication entry points and related modules.",
                    "depends_on": [],
                    "suggested_tool": "search_code",
                },
                {
                    "step_key": "review_tokens",
                    "title": "Review token validation",
                    "description": "Review token claims, expiry checks and user lookup behavior.",
                    "rationale": "Token validation is central to the authentication trust boundary.",
                    "expected_output": "An evidence-based explanation of token validation.",
                    "depends_on": ["find_auth"],
                    "suggested_tool": "inspect_source",
                },
            ],
            "completion_criteria": [
                "Authentication entry points are identified.",
                "Token validation behavior is explained.",
            ],
            "assumptions": ["The selected repository snapshot is the intended source of truth."],
        }
    )
    return AgentPlanningResult(
        proposal=proposal,
        provider="openai_compatible",
        model="test-planner-model",
    )


@pytest.fixture()
def mocked_planner(monkeypatch):
    calls = []

    async def fake_plan_goal(self, goal: str, *, max_steps: int):
        calls.append({"goal": goal, "max_steps": max_steps})
        return planned_result()

    monkeypatch.setattr(AgentOrchestrator, "plan_goal", fake_plan_goal)
    return calls


def test_agent_task_endpoints_require_authentication(agent_client: TestClient):
    assert agent_client.get("/api/v1/agents/tasks").status_code == 401
    assert agent_client.post(
        "/api/v1/agents/tasks",
        json={
            "repository_id": "00000000-0000-4000-8000-000000000001",
            "goal": "Review authentication behavior",
        },
    ).status_code == 401


def test_create_task_persists_plan_and_steps(
    agent_client: TestClient,
    mocked_planner,
):
    account = create_account(agent_client, "agent-owner@example.com")
    repository = create_saved_repository(agent_client, account["headers"])
    mark_repository_indexed(agent_client, repository["id"])

    response = agent_client.post(
        "/api/v1/agents/tasks",
        headers=account["headers"],
        json={
            "repository_id": repository["id"],
            "goal": "Review authentication and explain token validation.",
            "max_steps": 5,
        },
    )

    assert response.status_code == 201, response.text
    task = response.json()
    assert task["status"] == "planned"
    assert task["repository_id"] == repository["id"]
    assert task["plan"]["summary"].startswith("Inspect the authentication")
    assert task["plan"]["planner_model"] == "test-planner-model"
    assert len(task["steps"]) == 2
    assert task["steps"][1]["depends_on"] == ["find_auth"]
    assert mocked_planner == [{
        "goal": "Review authentication and explain token validation.",
        "max_steps": 5,
    }]

    listed = agent_client.get("/api/v1/agents/tasks", headers=account["headers"])
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == task["id"]

    detail = agent_client.get(
        f"/api/v1/agents/tasks/{task['id']}",
        headers=account["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["plan"]["version"] == 1
    assert len(detail.json()["steps"]) == 2


def test_task_and_repository_are_isolated_between_users(
    agent_client: TestClient,
    mocked_planner,
):
    owner = create_account(agent_client, "agent-first@example.com")
    repository = create_saved_repository(agent_client, owner["headers"])
    mark_repository_indexed(agent_client, repository["id"])

    created = agent_client.post(
        "/api/v1/agents/tasks",
        headers=owner["headers"],
        json={
            "repository_id": repository["id"],
            "goal": "Review authentication and token behavior.",
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    other = create_account(agent_client, "agent-second@example.com")
    assert agent_client.get(
        f"/api/v1/agents/tasks/{task_id}",
        headers=other["headers"],
    ).status_code == 404
    assert agent_client.get(
        "/api/v1/agents/tasks",
        headers=other["headers"],
    ).json() == []
    assert agent_client.post(
        "/api/v1/agents/tasks",
        headers=other["headers"],
        json={
            "repository_id": repository["id"],
            "goal": "Review authentication and token behavior.",
        },
    ).status_code == 404


def test_task_creation_requires_indexed_repository(
    agent_client: TestClient,
    mocked_planner,
):
    account = create_account(agent_client, "agent-unindexed@example.com")
    repository = create_saved_repository(agent_client, account["headers"])

    response = agent_client.post(
        "/api/v1/agents/tasks",
        headers=account["headers"],
        json={
            "repository_id": repository["id"],
            "goal": "Review authentication and token behavior.",
        },
    )
    assert response.status_code == 409
    assert "Index the repository" in response.json()["detail"]
    assert mocked_planner == []


def test_task_creation_validates_request_and_missing_repository(agent_client: TestClient):
    account = create_account(agent_client, "agent-validation@example.com")

    invalid = agent_client.post(
        "/api/v1/agents/tasks",
        headers=account["headers"],
        json={
            "repository_id": "00000000-0000-4000-8000-000000000001",
            "goal": "one",
            "shell": "should-not-be-accepted",
        },
    )
    assert invalid.status_code == 422

    missing = agent_client.post(
        "/api/v1/agents/tasks",
        headers=account["headers"],
        json={
            "repository_id": "00000000-0000-4000-8000-000000000001",
            "goal": "Review authentication and token behavior.",
        },
    )
    assert missing.status_code == 404


def test_task_cancellation_changes_state_and_repeated_cancel_is_rejected(
    agent_client: TestClient,
    mocked_planner,
):
    account = create_account(agent_client, "agent-cancel@example.com")
    repository = create_saved_repository(agent_client, account["headers"])
    mark_repository_indexed(agent_client, repository["id"])
    created = agent_client.post(
        "/api/v1/agents/tasks",
        headers=account["headers"],
        json={
            "repository_id": repository["id"],
            "goal": "Review authentication and token behavior.",
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    cancelled = agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/cancel",
        headers=account["headers"],
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    repeated = agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/cancel",
        headers=account["headers"],
    )
    assert repeated.status_code == 409


def test_planner_configuration_failure_returns_service_unavailable(
    agent_client: TestClient,
    monkeypatch,
):
    from app.services.llm import LLMConfigurationError

    account = create_account(agent_client, "agent-disabled@example.com")
    repository = create_saved_repository(agent_client, account["headers"])
    mark_repository_indexed(agent_client, repository["id"])

    async def fail_configuration(self, goal: str, *, max_steps: int):
        raise LLMConfigurationError("Provider is disabled for this test.")

    monkeypatch.setattr(AgentOrchestrator, "plan_goal", fail_configuration)
    response = agent_client.post(
        "/api/v1/agents/tasks",
        headers=account["headers"],
        json={
            "repository_id": repository["id"],
            "goal": "Review authentication and token behavior.",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Provider is disabled for this test."



def test_read_only_tool_catalog_and_execution_are_owner_scoped(
    agent_client: TestClient,
    mocked_planner,
    monkeypatch,
):
    from app.agents import execution as execution_service

    account = create_account(agent_client, "agent-tools-owner@example.com")
    repository = create_saved_repository(agent_client, account["headers"])
    mark_repository_indexed(agent_client, repository["id"])
    created = agent_client.post(
        "/api/v1/agents/tasks",
        headers=account["headers"],
        json={
            "repository_id": repository["id"],
            "goal": "Inspect repository metadata and review authentication.",
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()

    catalog = agent_client.get(
        f"/api/v1/agents/tasks/{task['id']}/tools",
        headers=account["headers"],
    )
    assert catalog.status_code == 200
    assert {tool["name"] for tool in catalog.json()} == {
        "repository_overview",
        "list_indexed_files",
        "search_code",
        "inspect_source",
    }
    assert all(tool["read_only"] is True for tool in catalog.json())

    other = create_account(agent_client, "agent-tools-other@example.com")
    assert agent_client.get(
        f"/api/v1/agents/tasks/{task['id']}/tools",
        headers=other["headers"],
    ).status_code == 404
    assert agent_client.get(
        f"/api/v1/agents/tasks/{task['id']}/tool-executions",
        headers=other["headers"],
    ).status_code == 404

    async def choose_tool(task_arg, step_arg, registry, *, instruction=None):
        if step_arg.step_key == "find_auth":
            return LLMFunctionCall(
                call_id="call-overview-1",
                name="repository_overview",
                arguments={},
            )
        return LLMFunctionCall(
            call_id="call-files-2",
            name="list_indexed_files",
            arguments={"limit": 5},
        )

    monkeypatch.setattr(execution_service, "select_tool_call", choose_tool)

    blocked = agent_client.post(
        f"/api/v1/agents/tasks/{task['id']}/steps/review_tokens/execute",
        headers=account["headers"],
        json={},
    )
    assert blocked.status_code == 409
    assert "prerequisite" in blocked.json()["detail"]

    first = agent_client.post(
        f"/api/v1/agents/tasks/{task['id']}/steps/find_auth/execute",
        headers=account["headers"],
        json={"instruction": "Start with repository metadata."},
    )
    assert first.status_code == 200, first.text
    first_result = first.json()
    assert first_result["tool_name"] == "repository_overview"
    assert first_result["status"] == "succeeded"
    assert first_result["tool_output"]["repository"] == "digvijay1129/repolens"
    assert first_result["tool_output"]["source_execution"].startswith("disabled")

    repeated = agent_client.post(
        f"/api/v1/agents/tasks/{task['id']}/steps/find_auth/execute",
        headers=account["headers"],
        json={},
    )
    assert repeated.status_code == 409

    second = agent_client.post(
        f"/api/v1/agents/tasks/{task['id']}/steps/review_tokens/execute",
        headers=account["headers"],
        json={},
    )
    assert second.status_code == 200, second.text
    assert second.json()["tool_name"] == "list_indexed_files"

    history = agent_client.get(
        f"/api/v1/agents/tasks/{task['id']}/tool-executions",
        headers=account["headers"],
    )
    assert history.status_code == 200
    assert len(history.json()) == 2
    assert {item["status"] for item in history.json()} == {"succeeded"}


def test_failed_tool_call_is_logged_and_step_can_be_retried(
    agent_client: TestClient,
    mocked_planner,
    monkeypatch,
):
    from app.agents import execution as execution_service

    account = create_account(agent_client, "agent-tool-failure@example.com")
    repository = create_saved_repository(agent_client, account["headers"])
    mark_repository_indexed(agent_client, repository["id"])
    created = agent_client.post(
        "/api/v1/agents/tasks",
        headers=account["headers"],
        json={
            "repository_id": repository["id"],
            "goal": "Inspect repository metadata and review authentication.",
        },
    )
    task_id = created.json()["id"]

    async def fail_selection(task_arg, step_arg, registry, *, instruction=None):
        return LLMFunctionCall(
            call_id="call-unknown-tool",
            name="execute_shell",
            arguments={"command": "whoami"},
        )

    monkeypatch.setattr(execution_service, "select_tool_call", fail_selection)
    failed = agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/steps/find_auth/execute",
        headers=account["headers"],
        json={},
    )
    assert failed.status_code == 502
    assert "not available" in failed.json()["detail"]

    history = agent_client.get(
        f"/api/v1/agents/tasks/{task_id}/tool-executions",
        headers=account["headers"],
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["status"] == "failed"
    assert history.json()[0]["error_message"]
