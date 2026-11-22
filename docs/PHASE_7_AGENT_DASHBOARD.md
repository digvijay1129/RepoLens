# Phase 7 — Agent Dashboard and UI

**Status:** Implemented on `main`  
**Frontend route:** `/agents`  
**Scope:** Integrated authenticated agent workspace for task creation, execution progress, specialist assignments, human approvals, repository memory and tool audit history.

## Goal

Expose the Phase 1–6 autonomous agent backend through the existing React application. Phase 7 extends the current RepoLens workspace and design system; it does not create a separate frontend application or change the API authentication model.

## Navigation

The authenticated workspace sidebar includes **Agent workspace**, which opens `/agents`. The page inherits the existing workspace shell, theme setting, authenticated user and saved-repository state.

## Dashboard areas

### Task creation and task list

- Select one of the user's saved repositories.
- Create a task from a natural-language goal.
- Choose `auto` or `approve_each` execution control.
- Set the maximum planned steps (4–20).
- Browse recent tasks and their lifecycle status.
- Task creation is disabled until the selected repository has an indexed commit.

### Execution

- Inspect the persisted plan, descriptions, dependencies and status of each step.
- View completion progress and tool-call totals.
- Start planned tasks, resume paused or approved tasks, and cancel non-terminal work.
- Review the coordinator's final task report and specialist findings when complete.
- Refresh task details after user actions and when the workspace regains focus.

The UI calls the existing bounded run/resume endpoints. It does not start a second client-side execution engine or bypass backend budgets and policy checks.

### Agent team

- View the Main Coordinator Agent.
- View the five fixed specialist roles and their mission/capability summary.
- Inspect per-step assignments, completion state and delegation count.
- View specialist attempt status in the audit history.

### Human approval center

- Display the exact proposed tool name and validated JSON arguments.
- Show the specialist, policy reason, request expiry and action-hash fingerprint.
- Approve or deny a pending action through the Phase 6 endpoints.
- After approval, resume the task to execute the exact stored action.
- Display the decision result and historical approval status.

The UI cannot edit an approval payload, change an action hash, or execute an action directly from the approval card. The backend remains the enforcement boundary.

### Repository memory

Memory management is available independently of an existing task:

- Add user-curated notes, architecture, convention, decision and troubleshooting memories.
- Search the selected repository's memories.
- Include archived and expired records in the management view.
- Archive, restore or permanently delete a memory.
- View importance, retrieval count and last update metadata.

Repository memory can be accessed before source indexing. Autonomous task creation still requires an indexed repository snapshot.

### Tool history

- Inspect registered read-only tool calls.
- View tool status, timestamp, duration and specialist.
- Expand the exact recorded input and structured output.
- Inspect safe error text for failed executions.
- Review delegation attempts and their assigned plan steps.

## Frontend API client

The existing `frontend/src/lib/api.js` client now includes owner-authenticated wrappers for:

- Agent task list, creation, detail, run, resume and cancellation.
- Team and specialist delegation records.
- Tool execution history.
- Approval list, approve and deny.
- Repository memory list, create, update/archive/restore and delete.

The wrappers use the shared API base URL, bearer-token attachment, response parsing and sanitized HTTP error handling. No access token or provider secret is stored in dashboard component state.

## Responsive behavior

The dashboard uses the existing CSS variables, dark/light theme, panels, buttons and typography. The task list/sidebar and detail workspace collapse into a single column on narrower screens. Metrics, forms, tables, approval cards and memory controls wrap for tablet/mobile widths. Tab navigation remains horizontally scrollable on narrow screens.

## Verification

Frontend tests cover:
- Creating a task with `approve_each` mode.
- Rendering an exact pending action and recording owner approval.
- Recording denial through the approval center.
- Saving a user-curated repository memory.
- Opening repository memory before any agent task exists.
- API request paths, payloads, authorization headers and query filters.

The production build verifies route integration and the full application bundle. The repository CI workflow also runs the backend/PostgreSQL regression suite and creates a validated source-only release archive.

## Local usage after all phases

1. Start PostgreSQL and apply all Alembic migrations.
2. Start the backend API and frontend development server using the root README instructions.
3. Sign in and connect a repository.
4. Index source files; task creation is enabled after the repository has an indexed commit.
5. Open **Agent workspace** from the sidebar.
6. Create a task, select the approval mode and start execution.
7. Review specialist progress, approve/deny proposed actions, inspect memory and audit history, and review the final report.

Phase 7 adds no new tool permissions. Existing read-only tool allowlists, owner checks, approval gates, task budgets, snapshot validation and server-side execution rules remain in force.
