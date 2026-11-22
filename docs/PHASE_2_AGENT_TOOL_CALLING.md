# Phase 2 — Agent Tool Calling System

**Status:** Implemented on `main`  
**Migration:** `20261122_0009`  
**Scope:** Read-only tool registry, OpenAI-compatible function calling, individual planned-step execution, and tool audit history.

## Goal

Connect the Phase 1 planner to controlled, real repository operations without introducing an unrestricted shell, filesystem writer, or remote GitHub mutation capability.

Phase 2 supports one selected tool call for one user-triggered planned step. It does not implement the autonomous multi-step execution loop; that is Phase 3.

## Architecture

```text
Authenticated user
    |
    v
POST /api/v1/agents/tasks/{task_id}/steps/{step_key}/execute
    |
    v
Owner-scoped task + current indexed commit + dependency checks
    |
    v
OpenAI-compatible function calling (exactly one call)
    |
    v
AgentToolRegistry
    |
    +--> Validate function name against fixed allowlist
    +--> Validate JSON arguments with Pydantic schema
    +--> Execute read-only repository adapter
    |
    v
Persist result, duration, status and provider call ID
    |
    v
Return structured result and source citations
```

## Registered read-only tools

| Tool | Function |
|---|---|
| `repository_overview` | Read repository metadata, selected commit, indexed file and chunk counts |
| `list_indexed_files` | List file paths and indexed line/chunk statistics for the current snapshot |
| `search_code` | Reuse RepoLens keyword, semantic or hybrid retrieval with citations |
| `inspect_source` | Read a bounded line range from an exact file in the current indexed snapshot |

Every tool receives its repository and user context from the authenticated backend, never from LLM-supplied arguments. Each tool query is restricted to the task's repository, owner and pinned commit.

The registry rejects unknown tools and validates arguments before dispatch. Only read-only tools can be registered in Phase 2. There is no shell tool, code execution tool, file writer or GitHub write operation.

## Tool calling

The existing LLM provider configuration is reused. The OpenAI-compatible client sends:

- The current task goal and planned step.
- An optional user instruction for that single step.
- Function schemas generated from registered Pydantic argument models.
- `tool_choice=required` and `parallel_tool_calls=false`.

The provider response must contain exactly one function call with a JSON object. The selected name must exist in the registry; the arguments must validate against that tool's Pydantic schema. Multiple calls, malformed JSON, unavailable tool names, invalid input and provider errors are rejected.

The tool selection prompt treats task text and the optional user instruction as request data. It cannot expand the registered tool allowlist.

## Persistence and audit history

Migration `20261122_0009` adds `agent_tool_executions` and the composite unique key on `agent_steps` required for its ownership-preserving foreign key.

Every execution record includes:

- Owning task, planned step, repository and user.
- Provider function-call identifier (when supplied).
- Selected tool name and validated JSON arguments.
- Structured tool output or a safe error message.
- Running/succeeded/failed state, duration and timestamps.

A failed step can be retried manually. A succeeded step cannot be executed again. Prerequisite steps must have succeeded before a dependent step can run. Tool execution history is only visible to the owning user.

## API

All endpoints require an authenticated JWT bearer token.

### List available tools

`GET /api/v1/agents/tasks/{task_id}/tools`

Returns the registered tool names, descriptions, read-only classification and JSON parameter schemas.

### Execute one planned step

`POST /api/v1/agents/tasks/{task_id}/steps/{step_key}/execute`

Optional request body:

```json
{
  "instruction": "Start with repository metadata and list the authentication-related files."
}
```

The server verifies task ownership, task status, indexed commit identity, step ownership and dependencies before requesting one provider tool call and executing it.

### List tool execution history

`GET /api/v1/agents/tasks/{task_id}/tool-executions`

Returns the task's persisted tool call records, inputs, results, errors, durations and timestamps for the current user only.

## Database and verification

From `backend/` in a configured local environment:

```powershell
alembic upgrade head
alembic current
python -m app.db.schema_check
python -m pytest
```

Phase 2 CI also checks the migration against a live PostgreSQL/pgvector service, executes backend tests, and verifies frontend tests and production build.

Tests mock the provider tool-call response. They verify provider response parsing, exactly-one-call enforcement, malformed arguments, read-only tool schemas, indexed source access, task dependencies, tool audit persistence, authentication and owner isolation. They do not require a live LLM API key.

## Explicit non-goals

Phase 2 does not implement:

- Automatic traversal of the full plan.
- Replanning based on tool observations.
- Durable background workers or resumable multi-step execution.
- Semantic long-term agent memory.
- Filesystem writes, shell execution, repository code execution or remote GitHub mutations.
- Approval workflows, patch application or pull-request creation.
- Agent workspace UI.

Phase 3 introduces the bounded Plan → Act → Observe → Decide execution loop and task-level recovery controls.
