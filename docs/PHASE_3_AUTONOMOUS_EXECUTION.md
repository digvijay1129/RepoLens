# Phase 3 — Autonomous Execution Engine

**Status:** Implemented on `main`  
**Migration:** `20261122_0010`  
**Scope:** Bounded Plan → Act → Observe → Decide execution, dependency scheduling, retries, resumable checkpoints, cooperative cancellation and final results.

## Goal

Turn the persisted Phase 1 plan and Phase 2 read-only tool registry into an autonomous repository-analysis workflow. The engine advances through dependency-ready plan steps, lets the LLM select one registered tool at a time, observes the result, and continues until the plan is complete or a configured stopping condition is reached.

The engine remains read-only: it cannot execute repository code, invoke a shell, modify files, push commits, or create pull requests.

## Execution loop

```text
Authenticated request
    |
    v
Load owner-scoped task + verify pinned indexed commit
    |
    v
Check cancellation, runtime and tool-call budgets
    |
    v
Choose the next pending/failed step whose dependencies succeeded
    |
    v
Observe previous successful tool results
    |
    v
LLM selects exactly one registered tool
    |
    v
Validate tool name and Pydantic arguments
    |
    v
Execute read-only repository tool
    |
    v
Persist tool result, duration, attempt and step status
    |
    +---- retry failed step within its retry budget
    |
    +---- pause when runtime or call budget is reached
    |
    +---- stop when cancellation is requested
    |
    v
Build a structured completion result when every step succeeds
```

## Durable checkpoints

Migration `20261122_0010` extends `agent_tasks` with:

- `max_tool_calls`: task-wide maximum tool-selection calls (1–40; defaults to 20).
- `max_retries_per_step`: retry allowance for each failed step (0–2; defaults to 1).
- `total_tool_calls` and `total_retries`: cumulative counters that are not reset on resume.
- `final_result`: structured completion report.
- `execution_started_at` and `execution_finished_at`: run lifecycle timestamps.

Each Phase 2 tool attempt is already stored in `agent_tool_executions`; each step's persisted status records progress. Successful steps are never repeated during a normal resume. Failed steps are retried only within the configured allowance.

## Task lifecycle

`planned → running → completed`

A task can also move from `running` to:

- `paused` when the per-run runtime or task-wide tool-call budget is reached. The owner can resume with a larger remaining budget.
- `cancelled` when the owner requests cancellation. Cancellation is cooperative: the current read-only call is allowed to finish, and the runner checks the state before starting another call.
- `failed` when a step exhausts its retry allowance, the repository snapshot changes, the provider is not configured, or the plan cannot make progress.

A paused or interrupted task can resume. If a process stops while a task or step is persisted as `running`, the resume path waits for a stale-run window (four minutes since the last task update) before marking unfinished calls as interrupted failures and recovering the step within its retry budget. A recently updated running task is treated as active and cannot be started twice.

## Budgets

The run request supports:

| Field | Range | Default |
|---|---:|---:|
| `max_tool_calls` | 1–40 | Existing task limit (20 for new tasks) |
| `max_retries_per_step` | 0–2 | 1 |
| `max_runtime_seconds` | 5–180 | 90 |

The tool-call counter is cumulative for the task, including calls made through the Phase 2 individual-step endpoint. A resume request may raise the task limit up to 40, but it does not reset the number of calls already consumed.

The runtime ceiling is checked between tool calls. A currently executing provider request may finish after the elapsed-time budget is reached; provider request timeout settings still apply.

## API

All routes are under `/api/v1` and require an authenticated JWT bearer token. Task ownership is verified on every operation.

### Start autonomous execution

`POST /api/v1/agents/tasks/{task_id}/run`

Example:

```json
{
  "max_tool_calls": 12,
  "max_retries_per_step": 1,
  "max_runtime_seconds": 90
}
```

Starts a planned task and returns its current or terminal task detail, including all step statuses, budget counters, timestamps and final result when completed.

### Resume a paused or interrupted task

`POST /api/v1/agents/tasks/{task_id}/resume`

Accepts the same optional budget fields. Supply a higher `max_tool_calls` value when the task paused because it reached its previous cumulative limit.

### Cancel a task

`POST /api/v1/agents/tasks/{task_id}/cancel`

The owner can cancel queued, planning, planned, running or paused tasks. A cancellation received during a tool call is applied between calls.

### Inspect progress

`GET /api/v1/agents/tasks/{task_id}`

Returns task status, step progress, tool-call/retry counters, timestamps and the structured final result.

`GET /api/v1/agents/tasks/{task_id}/tool-executions`

Returns the audit history of each selected tool, validated inputs, outputs or safe errors, duration and timestamps.

## Final result

On successful completion, `final_result` contains:

- Original goal and planner summary.
- Plan completion criteria.
- The latest successful tool result for each completed step.
- Total tool calls, retries and the pinned indexed commit SHA.

The completion report is assembled deterministically from persisted tool results; it does not claim that a separate LLM verified the completion criteria. Review the returned evidence before treating a repository conclusion as authoritative.

## Operational model

The run and resume endpoints execute the bounded loop inside the HTTP request. They are not a background queue or durable worker service. The engine commits every tool attempt and step result, so a later resume can recover checkpoints, but a client or server request timeout can still interrupt the HTTP response while persisted state remains inspectable.

A future worker/queue phase can move long-running orchestration out of the request lifecycle without changing the registered read-only tools.

## Verification

CI runs:

- The Phase 3 Alembic migration against a live PostgreSQL/pgvector database.
- The database schema checker against all application tables and named constraints.
- HTTP tests for dependency ordering, tool observations, successful multi-step completion, budget pause/resume, retries, cancellation and owner isolation.
- Existing Phase 1/2 agent tests, all backend tests, frontend unit tests and production build.
- Source-only release archive validation.

Provider function calls are mocked in tests. CI does not require an external LLM API key.

## Safety boundaries

- Tool selection only uses the fixed Phase 2 allowlist.
- Every argument is validated against the registered Pydantic schema.
- All tools are read-only and limited to the authenticated user's repository and the task's pinned commit.
- Retrieved source and prior tool observations are untrusted data, not instructions.
- Tool call, retry and runtime budgets are bounded.
- Task and tool audit records remain owner-scoped.
- No shell, code execution, filesystem write, repository mutation or GitHub write tool is registered.

## Explicit non-goals

Phase 3 does not add a durable background worker, long-term agent memory, multiple collaborating agents, code modification, automatic patch generation, pull-request creation or a frontend agent console. These remain later phases.
