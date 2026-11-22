# Phase 4 — Agent Memory System

**Status:** Implemented on `main`  
**Migration:** `20261122_0011`  
**Scope:** Owner-scoped repository memory, curated notes and decisions, automatic bounded observations, lexical relevance retrieval, provenance, deduplication, expiry and user-controlled lifecycle.

## Goal

Give RepoLens agents durable repository context that can be reused across tasks without treating memory as executable instructions or copying unbounded source-code excerpts into a separate store.

The memory layer is repository-scoped and owner-scoped. It is distinct from:
- The current task plan and its step statuses.
- The Phase 3 tool-execution audit log.
- The repository source index and its original line-addressable chunks.

## Memory record

Migration `20261122_0011` creates `agent_memories` with:

| Field | Purpose |
|---|---|
| `user_id`, `repository_id` | Enforce workspace and repository ownership |
| `task_id`, `source_execution_id` | Optional task/tool-call provenance |
| `memory_type` | Architecture, convention, decision, troubleshooting, note or observation |
| `origin` | User-curated or automatically captured by the agent |
| `title`, `content`, `tags` | Searchable memory text and labels |
| `source_refs`, `source_commit_sha` | Citation pointers and indexed snapshot provenance |
| `content_hash` | Deduplicate equivalent records within one user's repository |
| `confidence`, `importance` | Retrieval ranking signals |
| `is_active`, `expires_at` | Lifecycle, retention and expiry controls |
| `access_count`, `last_accessed_at` | Retrieval usage metadata |
| `created_at`, `updated_at` | Audit timestamps |

Database constraints enforce allowed memory types/origins, bounded title/content lengths, confidence and importance ranges, a unique content hash per owner/repository, and foreign keys tying task memories to the same repository owner.

## Memory capture

Successful read-only tool calls create a compact observation when useful:

- Repository overview → repository language and indexed snapshot/file/chunk metadata.
- Code search → query, result count and file/line citation pointers.
- Source inspection → file/line reference and task-step context.
- Indexed file listing → bounded path-inventory metadata.

Automatic memories are tagged with origin `agent`, confidence 0.75, low-to-medium importance and a 30-day expiry. Repeated equivalent observations refresh the existing record instead of creating unlimited duplicates.

The memory capture path deliberately does **not** copy raw source excerpts into memory. Original source remains in the indexed chunk store and is reached through citation pointers. Automatic capture is best-effort: it never changes the result or status of a successful tool execution.

## User-curated memory

Users can add durable architecture notes, conventions, design decisions, troubleshooting notes and general repository notes. User-created memories do not expire unless an expiry is explicitly supplied. Each active repository is limited to 250 memories, including both user and automatic records. Each memory is bounded to 6,000 characters, 12 tags, and a small citation-reference list.

Users can edit allowed fields, archive/restore memories with `is_active`, and permanently delete memories. Archived and expired records are excluded from normal retrieval but can be inspected through `include_inactive=true` for cleanup. Ownership, origin, task provenance and execution provenance are not writable through the public API.

## Retrieval and agent context

Before each read-only tool call, the execution service searches active, non-expired memories for the authenticated user and selected repository. It ranks results using:
- Token overlap in title, content and tags.
- Exact phrase match.
- Importance and confidence.
- Recency.
- A penalty when a memory's source commit differs from the task's pinned commit.

At most six relevant memories are injected into the next tool-selection context. They are labelled as untrusted contextual data, not instructions. Repository memories cannot expand the tool allowlist or bypass Pydantic argument validation. The original source citation and commit provenance are retained to help the agent distinguish a current snapshot from an older observation.

Retrieval is lexical and metadata-ranked in this phase; it does not require embedding API calls or add another vector index.

## API

All routes require the authenticated JWT bearer token and enforce workspace ownership.

### List and search repository memories

`GET /api/v1/agents/repositories/{repository_id}/memories`

Optional query parameters:
- `query`: lexical relevance search.
- `memory_type`: filter by memory type.
- `include_inactive`: include inactive entries (expired records remain excluded).
- `limit`: 1–100, default 50.

### Create a user-curated memory

`POST /api/v1/agents/repositories/{repository_id}/memories`

Example:

```json
{
  "memory_type": "convention",
  "title": "Authentication module locations",
  "content": "Authentication routes are in backend/app/api/routes/auth.py and token validation is in backend/app/services/auth.py.",
  "tags": ["authentication", "jwt", "backend"],
  "importance": 4,
  "confidence": 1.0
}
```

### Update a memory

`PATCH /api/v1/agents/memories/{memory_id}`

Only `memory_type`, `title`, `content`, `tags`, `importance`, `confidence`, `is_active` and `expires_at` are editable. Set `"is_active": false` to archive or `true` to restore. Send `"expires_at": null` to remove an expiry date.

### Permanently delete a memory

`DELETE /api/v1/agents/memories/{memory_id}`

Returns HTTP 204 after deletion. Other users receive 404 for foreign repository or memory IDs.

## Limits and privacy

- Up to 250 active memories per repository.
- Memory content up to 6,000 characters; at most 12 tags.
- Automatic memory expiry: 30 days.
- Retrieval returns at most six records to a tool-selection request.
- Memory retrieval only queries the selected repository and authenticated user.
- Raw source snippets are not copied into automatic memory.
- User memory text and automatically captured observations are treated as untrusted context when passed to the LLM.
- Source references and commit SHA remain available for verification.
- No provider key, cross-user/global memory search, unrestricted code execution or external memory service is introduced.

## Verification

CI applies migration `20261122_0011` to a live PostgreSQL/pgvector database and validates all application tables, columns, indexes and named constraints. Tests cover:
- Model registration and owner/provenance foreign keys.
- Memory create/list/search/update/delete and content deduplication.
- Cross-user isolation.
- Schema and payload validation.
- Automatic memory capture after a successful tool call.
- Injection of relevant stored memory into autonomous tool-selection context.
- Existing Phase 1–3 agent execution, retry, cancellation and resume behavior.

The LLM provider is mocked in the test suite; no external LLM API key is needed for CI.
