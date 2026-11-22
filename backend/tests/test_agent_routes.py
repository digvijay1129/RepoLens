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

    async def choose_tool(task_arg, step_arg, registry, *, instruction=None, observations=None):
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

    async def fail_selection(task_arg, step_arg, registry, *, instruction=None, observations=None):
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



def _create_agent_task_for_run(client: TestClient, headers: dict) -> str:
    repository = create_saved_repository(client, headers)
    mark_repository_indexed(client, repository["id"])
    created = client.post(
        "/api/v1/agents/tasks",
        headers=headers,
        json={
            "repository_id": repository["id"],
            "goal": "Inspect repository metadata and review authentication.",
            "max_steps": 5,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_autonomous_run_executes_dependencies_and_builds_final_result(
    agent_client: TestClient,
    mocked_planner,
    monkeypatch,
):
    from app.agents import execution as execution_service

    account = create_account(agent_client, "agent-autonomous-owner@example.com")
    task_id = _create_agent_task_for_run(agent_client, account["headers"])
    selection_calls = []

    async def choose_tool(task, step, registry, *, instruction=None, observations=None):
        selection_calls.append({
            "step_key": step.step_key,
            "observations": observations or [],
        })
        if step.step_key == "find_auth":
            return LLMFunctionCall(
                call_id="auto-call-1",
                name="repository_overview",
                arguments={},
            )
        return LLMFunctionCall(
            call_id="auto-call-2",
            name="list_indexed_files",
            arguments={"limit": 10},
        )

    monkeypatch.setattr(execution_service, "select_tool_call", choose_tool)
    response = agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/run",
        headers=account["headers"],
        json={
            "max_tool_calls": 4,
            "max_retries_per_step": 0,
            "max_runtime_seconds": 15,
        },
    )

    assert response.status_code == 200, response.text
    task = response.json()
    assert task["status"] == "completed"
    assert task["total_tool_calls"] == 2
    assert task["total_retries"] == 0
    assert [step["status"] for step in task["steps"]] == ["succeeded", "succeeded"]
    assert task["final_result"]["execution"]["status"] == "completed"
    assert len(task["final_result"]["completed_steps"]) == 2
    assert selection_calls[0]["step_key"] == "find_auth"
    assert selection_calls[1]["step_key"] == "review_tokens"
    assert selection_calls[1]["observations"][0]["tool_name"] == "repository_overview"


def test_autonomous_run_pauses_at_budget_and_resumes_without_repeating_success(
    agent_client: TestClient,
    mocked_planner,
    monkeypatch,
):
    from app.agents import execution as execution_service

    account = create_account(agent_client, "agent-resume-owner@example.com")
    task_id = _create_agent_task_for_run(agent_client, account["headers"])
    selected_steps = []

    async def choose_tool(task, step, registry, *, instruction=None, observations=None):
        selected_steps.append(step.step_key)
        return LLMFunctionCall(
            call_id=f"resume-{len(selected_steps)}",
            name="repository_overview",
            arguments={},
        )

    monkeypatch.setattr(execution_service, "select_tool_call", choose_tool)
    paused = agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/run",
        headers=account["headers"],
        json={
            "max_tool_calls": 1,
            "max_retries_per_step": 0,
            "max_runtime_seconds": 15,
        },
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "paused"
    assert paused.json()["total_tool_calls"] == 1
    assert paused.json()["steps"][0]["status"] == "succeeded"
    assert paused.json()["steps"][1]["status"] == "pending"

    completed = agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/resume",
        headers=account["headers"],
        json={
            "max_tool_calls": 3,
            "max_retries_per_step": 0,
            "max_runtime_seconds": 15,
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["total_tool_calls"] == 2
    assert selected_steps == ["find_auth", "review_tokens"]


def test_autonomous_run_retries_failed_tool_within_budget(
    agent_client: TestClient,
    mocked_planner,
    monkeypatch,
):
    from app.agents import execution as execution_service

    account = create_account(agent_client, "agent-retry-owner@example.com")
    task_id = _create_agent_task_for_run(agent_client, account["headers"])
    calls = {"count": 0}

    async def choose_tool(task, step, registry, *, instruction=None, observations=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return LLMFunctionCall(
                call_id="retry-invalid-tool",
                name="execute_shell",
                arguments={"command": "unsafe"},
            )
        return LLMFunctionCall(
            call_id=f"retry-valid-{calls['count']}",
            name="repository_overview",
            arguments={},
        )

    monkeypatch.setattr(execution_service, "select_tool_call", choose_tool)
    response = agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/run",
        headers=account["headers"],
        json={
            "max_tool_calls": 4,
            "max_retries_per_step": 1,
            "max_runtime_seconds": 15,
        },
    )

    assert response.status_code == 200, response.text
    task = response.json()
    assert task["status"] == "completed"
    assert task["total_tool_calls"] == 3
    assert task["total_retries"] == 1
    assert calls["count"] == 3
    assert task["steps"][0]["status"] == "succeeded"


def test_autonomous_run_and_cancel_are_owner_scoped(
    agent_client: TestClient,
    mocked_planner,
):
    owner = create_account(agent_client, "agent-run-isolation-owner@example.com")
    task_id = _create_agent_task_for_run(agent_client, owner["headers"])
    other = create_account(agent_client, "agent-run-isolation-other@example.com")

    assert agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/run",
        headers=other["headers"],
        json={},
    ).status_code == 404
    assert agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/cancel",
        headers=other["headers"],
    ).status_code == 404


def test_running_task_can_be_cancelled_and_is_terminal(
    agent_client: TestClient,
    mocked_planner,
):
    from app.models.agent_task import AgentTask

    account = create_account(agent_client, "agent-running-cancel@example.com")
    task_id = _create_agent_task_for_run(agent_client, account["headers"])
    with Session(agent_client.app.state.agent_test_engine) as db:
        task = db.get(AgentTask, UUID(task_id))
        task.status = "running"
        db.commit()

    cancelled = agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/cancel",
        headers=account["headers"],
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    cannot_resume = agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/resume",
        headers=account["headers"],
        json={},
    )
    assert cannot_resume.status_code == 409



def test_repository_memory_crud_search_deduplication_and_owner_isolation(
    agent_client: TestClient,
):
    owner = create_account(agent_client, "agent-memory-owner@example.com")
    repository = create_saved_repository(agent_client, owner["headers"])
    base = f"/api/v1/agents/repositories/{repository['id']}/memories"

    created = agent_client.post(
        base,
        headers=owner["headers"],
        json={
            "memory_type": "architecture",
            "title": "Authentication architecture",
            "content": "Authentication uses signed JWT bearer tokens and validates issuer audience and expiry before loading the workspace user.",
            "tags": ["auth", "JWT", "backend"],
            "importance": 5,
            "confidence": 0.98,
        },
    )
    assert created.status_code == 201, created.text
    memory = created.json()
    assert memory["origin"] == "user"
    assert memory["memory_type"] == "architecture"
    assert memory["tags"] == ["auth", "jwt", "backend"]
    memory_id = memory["id"]

    duplicate = agent_client.post(
        base,
        headers=owner["headers"],
        json={
            "memory_type": "architecture",
            "title": "JWT authentication",
            "content": "Authentication uses signed JWT bearer tokens and validates issuer audience and expiry before loading the workspace user.",
            "tags": ["security"],
            "importance": 4,
        },
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == memory_id

    listed = agent_client.get(base, headers=owner["headers"])
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    searched = agent_client.get(
        base,
        headers=owner["headers"],
        params={"query": "JWT authentication issuer", "limit": 5},
    )
    assert searched.status_code == 200
    assert searched.json()[0]["id"] == memory_id
    assert searched.json()[0]["relevance_score"] > 0

    updated = agent_client.patch(
        f"/api/v1/agents/memories/{memory_id}",
        headers=owner["headers"],
        json={
            "title": "JWT session security",
            "importance": 4,
            "tags": ["security", "jwt"],
            "expires_at": None,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "JWT session security"
    assert updated.json()["importance"] == 4
    assert updated.json()["expires_at"] is None

    other = create_account(agent_client, "agent-memory-other@example.com")
    other_repo_access = agent_client.get(
        base,
        headers=other["headers"],
    )
    assert other_repo_access.status_code == 404
    assert agent_client.patch(
        f"/api/v1/agents/memories/{memory_id}",
        headers=other["headers"],
        json={"title": "Take over"},
    ).status_code == 404
    assert agent_client.delete(
        f"/api/v1/agents/memories/{memory_id}",
        headers=other["headers"],
    ).status_code == 404

    deleted = agent_client.delete(
        f"/api/v1/agents/memories/{memory_id}",
        headers=owner["headers"],
    )
    assert deleted.status_code == 204
    assert agent_client.get(base, headers=owner["headers"]).json() == []


def test_memory_api_rejects_invalid_types_and_unbounded_payloads(agent_client: TestClient):
    account = create_account(agent_client, "agent-memory-validation@example.com")
    repository = create_saved_repository(agent_client, account["headers"])
    base = f"/api/v1/agents/repositories/{repository['id']}/memories"

    invalid_type = agent_client.post(
        base,
        headers=account["headers"],
        json={
            "memory_type": "secret",
            "title": "Invalid memory",
            "content": "This memory should not be accepted because the type is invalid.",
        },
    )
    assert invalid_type.status_code == 422

    invalid_tag = agent_client.post(
        base,
        headers=account["headers"],
        json={
            "memory_type": "note",
            "title": "Invalid tag",
            "content": "This memory should not be accepted because one tag is too long.",
            "tags": ["x" * 60],
        },
    )
    assert invalid_tag.status_code == 422

    invalid_payload = agent_client.post(
        base,
        headers=account["headers"],
        json={
            "memory_type": "note",
            "title": "Valid title",
            "content": "This note should not accept fields that bypass provenance controls.",
            "origin": "agent",
            "source_execution_id": "00000000-0000-4000-8000-000000000001",
        },
    )
    assert invalid_payload.status_code == 422


def test_successful_tool_execution_automatically_captures_bounded_memory(
    agent_client: TestClient,
    mocked_planner,
    monkeypatch,
):
    from app.agents import execution as execution_service

    account = create_account(agent_client, "agent-auto-memory@example.com")
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

    async def choose_overview(task, step, registry, *, instruction=None, observations=None):
        return LLMFunctionCall(
            call_id="memory-overview-call",
            name="repository_overview",
            arguments={},
        )

    monkeypatch.setattr(execution_service, "select_tool_call", choose_overview)
    executed = agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/steps/find_auth/execute",
        headers=account["headers"],
        json={},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "succeeded"

    from app.agents.memory import capture_tool_execution_memory
    with Session(agent_client.app.state.agent_test_engine) as db:
        captured = capture_tool_execution_memory(
            db,
            task_id=UUID(task_id),
            user_id=UUID(account["user"]["id"]),
            execution_id=UUID(executed.json()["id"]),
        )
    assert captured is not None

    memory_response = agent_client.get(
        f"/api/v1/agents/repositories/{repository['id']}/memories",
        headers=account["headers"],
    )
    assert memory_response.status_code == 200
    assert len(memory_response.json()) == 1
    memory = memory_response.json()[0]
    assert memory["origin"] == "agent"
    assert memory["memory_type"] == "architecture"
    assert memory["source_execution_id"] == executed.json()["id"]
    assert memory["source_commit_sha"] == "a" * 40
    assert "Repository digvijay1129/repolens" in memory["content"]
    assert "def " not in memory["content"]


def test_autonomous_step_selection_receives_relevant_persisted_memory(
    agent_client: TestClient,
    mocked_planner,
    monkeypatch,
):
    from app.agents import execution as execution_service

    account = create_account(agent_client, "agent-memory-context@example.com")
    repository = create_saved_repository(agent_client, account["headers"])
    mark_repository_indexed(agent_client, repository["id"])
    created_memory = agent_client.post(
        f"/api/v1/agents/repositories/{repository['id']}/memories",
        headers=account["headers"],
        json={
            "memory_type": "convention",
            "title": "Authentication modules",
            "content": "Authentication entry points are defined in backend/app/api/routes/auth.py and token validation is implemented by backend/app/services/auth.py.",
            "tags": ["authentication", "jwt", "backend"],
            "importance": 5,
        },
    )
    assert created_memory.status_code == 201, created_memory.text

    created = agent_client.post(
        "/api/v1/agents/tasks",
        headers=account["headers"],
        json={
            "repository_id": repository["id"],
            "goal": "Review authentication entry points and token validation.",
        },
    )
    task_id = created.json()["id"]
    observed_contexts = []

    async def choose_tool(task, step, registry, *, instruction=None, observations=None):
        observed_contexts.append(observations or [])
        return LLMFunctionCall(
            call_id=f"memory-context-{len(observed_contexts)}",
            name="repository_overview",
            arguments={},
        )

    monkeypatch.setattr(execution_service, "select_tool_call", choose_tool)
    response = agent_client.post(
        f"/api/v1/agents/tasks/{task_id}/run",
        headers=account["headers"],
        json={
            "max_tool_calls": 4,
            "max_retries_per_step": 0,
            "max_runtime_seconds": 15,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    assert any(
        item.get("tool_name") == "repository_memory"
        and "backend/app/api/routes/auth.py" in str(item.get("result"))
        for item in observed_contexts[-1]
    )
