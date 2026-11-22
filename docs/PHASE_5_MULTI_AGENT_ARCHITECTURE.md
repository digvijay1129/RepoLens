# Phase 5 — Multi-Agent Architecture

**Status:** Implemented on `main`  
**Migration:** `20261122_0012`  
**Scope:** Main coordinator, five fixed specialist roles, deterministic plan-step routing, role-specific LLM context, persistent owner-scoped delegation history, task team inspection and coordinator synthesis.

## Goal

Split repository-analysis responsibilities into focused specialist roles while preserving the existing Phase 1–4 execution, ownership, memory and safety boundaries.

The Phase 5 team is a coordinator plus five specialists:

| Role | Responsibility |
|---|---|
| Main Coordinator Agent | Route persisted plan steps, enforce shared execution policy and consolidate findings |
| Repository Research Agent | Discover relevant files, modules and source locations |
| Code Analysis Agent | Trace implementation behavior, control flow, dependencies and code quality |
| Architecture Agent | Map module boundaries, interfaces, data flow and trade-offs |
| Debugging Agent | Investigate reported errors, failing tests and possible regressions |
| Documentation Agent | Collect verified behavior, configuration, API and usage evidence |

## Architecture

```text
Authenticated task + validated plan
    |
    v
Main Coordinator Agent
    |
    +--> Deterministic route from each plan step to a fixed specialist
              |
              +--> Repository Research Agent
              +--> Code Analysis Agent
              +--> Architecture Agent
              +--> Debugging Agent
              +--> Documentation Agent
                         |
                         v
              Shared specialist execution contract
              - same authenticated user
              - same saved repository
              - same pinned indexed commit
              - same read-only tool allowlist
              - same memory retrieval policy
                         |
                         v
              One validated tool call per plan step
                         |
                         v
              Persist delegation + tool audit result
                         |
                         v
              Coordinator gathers specialist findings
                         |
                         v
              Structured final team report
```

Specialists are focused execution roles, not independent security principals. They do not receive separate credentials or additional permissions. All five use the same allowlisted read-only repository tools through the existing Phase 2 execution service.

## Specialist routing

Routing is deterministic and runs against the validated plan-step title, description, rationale, expected output and suggested tool. The model does not create arbitrary roles or select an unregistered specialist.

- Debugging language (errors, tracebacks, regressions, failing tests) routes to Debugging.
- Documentation and API-guide work routes to Documentation.
- Architecture, component and data-flow work routes to Architecture.
- Implementation review, control-flow, dependency and security analysis routes to Code Analysis.
- Discovery and file-location tasks, or tasks without a stronger specialist signal, route to Research.

The selected specialist's fixed mission and role prompt are combined with the coordinator policy and current task-step context before the single tool-selection call. Retrieved repository content, memory and previous observations remain untrusted evidence.

## Persistent delegation records

Migration `20261122_0012` creates `agent_delegations`. Each assignment stores:

- Task, plan step, user and repository ownership.
- Specialist key, display name and mission.
- Assignment attempt number and bounded assignment context.
- Status, start/finish timestamps and safe error summary.
- The corresponding tool-execution ID and a bounded result summary.

The database checks allowed specialist names, statuses and attempt numbers. Composite foreign keys bind every delegation to the same task owner, repository and plan step. Each step allows at most three delegation attempts.

Failed specialist attempts remain auditable. Phase 3's retry limits still govern autonomous re-execution, and successful steps remain checkpointed rather than being repeated.

## API

All routes require an authenticated JWT bearer token and enforce task ownership.

### Inspect the team assigned to a task

`GET /api/v1/agents/tasks/{task_id}/team`

Returns the coordinator role, five registered specialists, deterministic step assignments, per-specialist progress, latest delegation details and delegation count.

### Inspect delegation history

`GET /api/v1/agents/tasks/{task_id}/delegations`

Returns the owner-scoped, chronological specialist assignment history, including attempts, statuses, execution references, result summaries and safe errors.

### Existing task execution

The existing endpoints remain in place:

- `POST /api/v1/agents/tasks/{task_id}/run`
- `POST /api/v1/agents/tasks/{task_id}/resume`
- `POST /api/v1/agents/tasks/{task_id}/steps/{step_key}/execute`

Every executed plan step is automatically assigned to a registered specialist. The existing tool-execution response records the specialist key/name in its audit input.

## Coordinator synthesis

When all steps succeed, the existing deterministic completion path adds a `team` section to `final_result` containing:

- Coordinator name.
- Specialist roster and per-role counts.
- Planned step-to-specialist assignments and step statuses.
- Number of persisted delegation attempts.
- A finding for each successful delegation, with its specialist, step key, status and bounded result summary.

This summary is derived from persisted tool results and delegation records. It does not claim an independent specialist verified code by running it, and it does not invent test results or changes.

## Execution model and limits

Phase 5 executes one specialist tool call at a time within the Phase 3 bounded HTTP run loop. It does not run concurrent specialist workers, background queues or independent agent processes. This keeps task budgets, cancellation, retry handling, memory retrieval and result checkpointing consistent with Phase 3.

The existing guardrails remain active:

- Maximum task tool-call budget and per-run time budget.
- Existing retry limit and three-attempt delegation ceiling.
- Owner-scoped task/repository/step checks.
- Pinned indexed-commit validation before each tool operation.
- Pydantic validation against the fixed read-only tool registry.
- No shell, repository code execution, file writes or GitHub mutations.

## Verification

CI applies migration `20261122_0012` to PostgreSQL and validates all application tables, columns, indexes and named constraints. Tests cover:

- Fixed deterministic routing to all five specialist roles.
- Specialist role prompt propagation into tool selection.
- Persisted successful and failed delegation records.
- Delegation history and team summary endpoints.
- Cross-user access isolation.
- Coordinator findings included in the final autonomous task result.
- Existing memory retrieval, automatic memory capture, bounded execution, retries, pause/resume and cancellation.

The LLM provider is mocked in tests; no live provider key is needed for CI.
