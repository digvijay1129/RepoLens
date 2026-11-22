# Phase 1 — Agent Foundation

**Status:** Implemented on `main`  
**Migration:** `20261122_0008`  
**Scope:** Task creation, validated plan generation, persistence, lifecycle state and authenticated task APIs.

## Goal

Add the foundation for agentic repository workflows without replacing RepoLens's existing GitHub, indexing, retrieval, RAG or authentication services.

Phase 1 creates a declarative task plan only. Tool registration and execution are deliberately out of scope until Phases 2 and 3.

## Architecture

```text
Authenticated user
    |
    v
POST /api/v1/agents/tasks
    |
    v
Owner-scoped saved repository + indexed commit check
    |
    v
AgentOrchestrator
    |
    v
Existing LLM client (OpenAI-compatible / OpenRouter)
    |
    v
Pydantic plan validation + deterministic policy checks
    |
    v
PostgreSQL: agent_tasks -> agent_plans -> agent_steps
```

### New backend modules

- `app/agents/schemas.py`: task statuses, goal request schema, plan and step schemas.
- `app/agents/planner.py`: LLM-backed JSON planner and deterministic policy validation.
- `app/agents/orchestrator.py`: orchestration boundary for the planning stage.
- `app/agents/state.py`: explicit task lifecycle transition rules.
- `app/agents/service.py`: task persistence, serialization, listing, retrieval and cancellation.
- `app/api/routes/agents.py`: authenticated task endpoints.
- `app/api/schemas/agents.py`: API schema exports.

### Persistence

Migration `20261122_0008` adds:

- `agent_tasks`: user goal, repository, immutable indexed commit SHA, state and maximum step count.
- `agent_plans`: versioned plan summary, assumptions, completion criteria and effective planner provider/model.
- `agent_steps`: ordered steps, expected outputs, dependencies, suggested tool labels and status.

Composite foreign keys tie each plan/step to the same task, repository and user. This reinforces workspace ownership at the database layer, in addition to authenticated API checks.

## API

All endpoints are under `/api/v1` and require a valid JWT bearer token.

### Create a planned task

`POST /api/v1/agents/tasks`

Request:

```json
{
  "repository_id": "00000000-0000-4000-8000-000000000000",
  "goal": "Review the authentication architecture and identify areas that need further security investigation.",
  "max_steps": 8
}
```

Requirements:

- The repository must belong to the authenticated user.
- The repository must have a completed indexed snapshot.
- The existing LLM chat provider must be enabled and configured.
- `max_steps` is between 1 and 20.

A successful request returns the persisted task, plan summary, completion criteria, assumptions and ordered steps.

### List tasks

`GET /api/v1/agents/tasks?repository_id={uuid}&limit=20`

Lists only the authenticated user's tasks. The repository filter is optional and the limit is bounded to 1–50.

### Inspect a task

`GET /api/v1/agents/tasks/{task_id}`

Returns a task, saved plan metadata and ordered steps only when the task belongs to the authenticated user.

### Cancel a task

`POST /api/v1/agents/tasks/{task_id}/cancel`

Phase 1 permits cancellation only while a task is queued, planning or planned. Terminal tasks cannot be restarted or cancelled again.

## Planner policy

The planner:

1. Uses the configured RepoLens LLM client; no second provider integration is introduced.
2. Requests one JSON object matching the Pydantic plan schema.
3. Rejects extra/unexpected fields, duplicate step keys, invalid or forward dependencies and excessive step counts.
4. Accepts only the currently reserved suggested tool labels: `repository_overview`, `search_code`, `inspect_source`, `explain_architecture` and `draft_report`.
5. Never executes a suggested tool.

The effective provider/model settings are recorded so OpenRouter overrides are reflected accurately.

## Task lifecycle

Supported persisted task states:

`queued` → `planning` → `planned` → future execution states (`running`, `awaiting_approval`, `completed`, `failed`, `cancelled`).

The state transition contract is in `app/agents/state.py`. Phase 1 only creates a planned task or cancels an eligible task. Running, approval and completion states are reserved for later phases.

## Configuration

No new environment variables or package dependencies are required. Configure the existing RAG chat settings in `backend/.env`:

```dotenv
OPENROUTER_API_KEY=your_private_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_CHAT_MODEL=your_supported_model
LLM_ENABLED=true
```

Keep provider credentials in the backend environment only. Planner requests may incur provider costs. Do not send source code the user is not authorized to share.

## Migration and verification

From `backend/`:

```powershell
alembic upgrade head
alembic current
python -m app.db.schema_check
python -m pytest
```

Focused agent tests:

```powershell
python -m pytest tests/test_agent_foundation.py tests/test_agent_state.py tests/test_agent_models.py tests/test_migrations.py
```

Planner unit tests use a mocked completion function. They do not require a live provider key or make network requests.

## Explicit non-goals

Phase 1 does not implement:

- Tool registry or executable tool adapters.
- Multi-step agent execution or retries.
- Durable queue workers, resumability or concurrent execution.
- Long-term semantic agent memory.
- Filesystem writes, shell execution or repository code execution.
- Approval UI or autonomous pull-request operations.
- Agent workspace frontend.

Those belong to later phases. Existing RepoLens RAG chat, source indexing and retrieval remain separate and available.
