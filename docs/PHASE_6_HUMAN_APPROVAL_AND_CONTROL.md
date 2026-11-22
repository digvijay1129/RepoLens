# Phase 6 — Human Approval and Control

**Status:** Implemented on `main`  
**Migration:** `20261122_0013`  
**Scope:** Task-level approval policy, exact-action approval gates, owner-only approve/deny controls, expiry, cancellation, immutable decision history and approval-aware autonomous resume.

## Goal

Allow the repository owner to review a proposed action before a specialist invokes a tool. Approval is an explicit control gate in the execution path; it does not add capabilities or grant tools permission to write to the repository.

All tools currently registered in RepoLens remain read-only. In `approve_each` mode every proposed tool call is gated so the human-in-the-loop path can be exercised now and reused if a future phase adds higher-impact operations.

## Approval modes

Task creation accepts `approval_mode`:

| Mode | Behavior |
|---|---|
| `auto` | Backward-compatible default; registered read-only tools execute immediately |
| `approve_each` | Every proposed tool call pauses for the repository owner's approval |

Example task-creation request:

```json
{
  "repository_id": "00000000-0000-4000-8000-000000000001",
  "goal": "Review the repository authentication flow.",
  "approval_mode": "approve_each",
  "max_steps": 8
}
```

The chosen mode is persisted on `agent_tasks` and returned in task summary/detail responses.

## Approval lifecycle

```text
Coordinator / specialist selects one registered tool
    |
    v
Validate tool name and Pydantic arguments
    |
    v
Persist the exact normalized action + SHA-256 digest
    |
    v
Task enters awaiting_approval
Tool handler is NOT invoked
    |
    +-------------------------------+
    |                               |
    v                               v
Owner approves                  Owner denies
    |                               |
    v                               v
Approval becomes approved       Approval becomes denied
    |                           Task becomes failed
    v                               |
Owner resumes task                  v
    |                           No tool invocation
    v
Re-check owner, tool schema, action hash,
approval expiry and pinned repository commit
    |
    v
Execute the exact stored tool + arguments once
    |
    v
Approval becomes executed and links to the tool result
```

## Exact-action binding

The approval request stores:
- The registered tool name.
- Normalized Pydantic-validated JSON arguments.
- Specialist key and the proposed tool-execution ID.
- Provider call ID and task/step/delegation references.
- A SHA-256 digest of the canonical tool name + arguments.
- The task's repository/owner relationship and approval expiry.

The approve endpoint revalidates the proposed execution and registered argument schema, checks the digest, confirms task ownership, and verifies that the repository is still indexed at the task's pinned commit.

After approval, resume loads the saved proposal and executes that exact tool name and argument object. It does not ask the LLM to select a replacement action. An approval cannot be reused for a second execution.

## Expiry, denial and cancellation

- Approval requests expire after 15 minutes.
- An expired request is marked `expired`, its task is stopped, and the proposed execution is marked failed without invoking the tool.
- A denied action is marked `denied`; the parent task is stopped. A denied action is not silently retried.
- Cancelling the parent task cancels pending or approved-but-not-executed requests and marks the proposed execution as not executed.
- A repository snapshot change invalidates the approval and stops the task.
- Repeated approve/deny decisions return HTTP 409; cross-user requests return HTTP 404.

The decision row is retained for audit. The API deliberately does not offer approval deletion or arbitrary updates.

## API

All routes require the authenticated JWT bearer token and enforce the owning task user.

### Create task with approval policy

`POST /api/v1/agents/tasks`

Supply `approval_mode: "auto"` or `"approve_each"`. Omitting the field preserves automatic execution.

### Start/resume execution

`POST /api/v1/agents/tasks/{task_id}/run`

`POST /api/v1/agents/tasks/{task_id}/resume`

In `approve_each` mode the run response returns task status `awaiting_approval` when a proposed action is waiting. A run cannot resume while any request remains pending. After approval, call the resume endpoint; the approved action executes before the coordinator advances.

### Individual planned step

`POST /api/v1/agents/tasks/{task_id}/steps/{step_key}/execute`

When the task uses `approve_each`, the endpoint returns HTTP 202 with `approval_required: true` and the newly created approval request. The tool handler has not run at that point.

### List approvals and decisions

`GET /api/v1/agents/tasks/{task_id}/approvals`

Returns the chronological approval history for the current user and task, including proposed action, hash, specialist, status, expiry, decision identity/comment and execution reference.

### Approve one exact action

`POST /api/v1/agents/approvals/{approval_id}/approve`

Example:

```json
{
  "comment": "Reviewed the proposed read-only repository inspection."
}
```

This records permission for the exact saved action. It does not itself run the action; the task must be resumed.

### Deny one action

`POST /api/v1/agents/approvals/{approval_id}/deny`

Example:

```json
{
  "comment": "Do not run this proposed action."
}
```

The task is stopped and the tool is not invoked.

### Cancel parent task

`POST /api/v1/agents/tasks/{task_id}/cancel`

Any pending or approved-but-not-executed approval requests are cancelled in the same database transaction.

## Database

Migration `20261122_0013`:
- Adds `approval_mode` to `agent_tasks`, constrained to `auto` or `approve_each`.
- Allows `awaiting_approval` as a recorded tool-execution status.
- Creates `agent_approval_requests` with exact action JSON, SHA-256 digest, owner/task/step/delegation/execution provenance, expiry and decision metadata.
- Adds task/status, user/status/expiry and step/history indexes.
- Enforces composite foreign keys so a request cannot cross task owner, repository or step boundaries.

Approval records have no public delete or patch endpoint. Decision endpoints only accept a request in pending state; each request is consumed once.

## Verification and safety boundaries

CI verifies:
- PostgreSQL migration and schema constraints at Alembic head `20261122_0013`.
- Default `auto` compatibility.
- No tool-handler invocation before approval.
- Owner-only approval/denial.
- One-time approval and execution of the exact saved action.
- Denial and expiry stop the task without executing the proposal.
- Parent cancellation cancels pending approvals.
- Tool allowlist, Pydantic validation and repository snapshot checks are repeated before execution.
- Existing Phase 1–5 plan, autonomous-run, memory and specialist workflows.

Human approval is not a privilege escalation. Phase 6 adds no shell execution, source modification, GitHub write, pull-request creation, secret access or new tool capability. Actual LLM calls remain mocked in CI.
