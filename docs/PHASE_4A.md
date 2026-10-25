# Phase 4A — Safe source ingestion, chunking, and indexing jobs

## Scope

Phase 4A turns the saved public GitHub repository into a bounded, versioned source snapshot that later retrieval and embedding phases can use. This slice performs no LLM calls, embedding generation, vector search, or source-code execution.

## Implemented

- Owner-scoped `POST /api/v1/repositories/saved/{repository_id}/index` queues a background indexing job.
- `GET /api/v1/repositories/saved/{repository_id}/jobs/{job_id}` returns progress only when both the saved repository and job belong to the signed-in user.
- Job states: `queued`, `running`, `completed`, `failed`, with attempted commit, progress message, file counters, skipped-file count, chunk count and safe error detail.
- Source collection is pinned to the selected branch's immutable commit SHA, so all chunks in one job refer to the same version.
- Recursive Git tree listings are rejected if GitHub reports truncation or the tree exceeds the internal cap.
- Source paths are filtered to supported text/code/config/documentation formats. Credential files, `.env*`, keys/certificates, binary artifacts, lockfiles, generated/vendor directories and common build outputs are excluded.
- File-size, total-source-byte and file-count limits prevent unbounded indexing.
- UTF-8 text blobs are decoded with strict validation; binary and oversized source blobs are skipped safely.
- Deterministic overlapping chunks carry path, language, chunk index, original line range, safe symbol names (Python AST plus conservative declaration patterns), SHA-256 content hash, and approximate token count.
- Chunks are stored in PostgreSQL with ownership-linked foreign keys, uniqueness per repo/commit/path/chunk index and non-negative range constraints.
- The last completed snapshot remains available if a later indexing attempt fails. The job only switches the repository's indexed commit after the new snapshot is complete.
- Re-indexing the same successful commit is idempotent and avoids duplicating chunks.
- The Code Explorer includes an indexing action, progress bar, job state, chunk count, skipped-file count and commit short SHA.

## Safety limits

Current implementation limits:
- Maximum recursive tree entries: 30,000. A tree truncated by GitHub is rejected rather than silently indexing incomplete paths.
- Maximum eligible files in one job: 40.
- Maximum single file size: 256 KiB.
- Maximum source bytes selected for one job: 5 MiB.
- Maximum chunk size: 4,000 characters with approximately 350 characters of overlap.
- UTF-8 text only; no file execution or imports.

Unsupported or over-limit files are skipped and counted. GitHub's unauthenticated API may apply rate limits; the job reports a safe error if the limit is reached. Narrowing the index scope and authenticated GitHub access can be added in a later phase.

## Local setup

1. Make sure PostgreSQL is running and `backend/.env` has a valid `DATABASE_URL`.
2. Generate and configure `JWT_SECRET_KEY` if this is a fresh local environment.
3. Activate the backend virtual environment and run:

```powershell
cd backend
alembic upgrade head
alembic current
python -m app.db.schema_check
pytest
```

4. In another terminal run frontend tests and the production build:

```powershell
cd frontend
npm test
npm run build
npm run dev
```

The new migration is `20261025_0004`, following Phase 3B's `20261025_0003`. Upgrade the current database in place; do not drop and recreate it.

## API flow

1. The authenticated user starts indexing for a saved repository.
2. FastAPI creates a queued job and schedules the worker.
3. The worker resolves the selected branch to a commit, reads the recursive Git tree, filters safe text files, retrieves bounded blob contents, and chunks their text.
4. The worker persists a commit-specific chunk snapshot and updates progress after each file.
5. Only after successful completion does the repository's `indexed_commit_sha` switch to the new commit and previous snapshots get removed.
6. The frontend polls the job endpoint and refreshes repository status on completion/failure.

## Verification checklist

- [ ] Start an index job for a saved repository and see progress update in the Code Explorer.
- [ ] Confirm chunks are stored in PostgreSQL with original line ranges and file paths.
- [ ] Confirm ignored paths and binary/oversized files are counted as skipped.
- [ ] Re-index the same commit and confirm no duplicate chunk rows are created.
- [ ] Simulate a GitHub rate-limit/upstream failure and confirm the old completed snapshot is kept.
- [ ] Confirm another user cannot read a job from a repository they do not own.
- [ ] Run backend tests, live PostgreSQL schema verification, frontend tests, and the Vite production build.

## Not included in Phase 4A

- Model provider credentials or embedding API calls
- pgvector storage/indexes, similarity or hybrid retrieval
- LLM answers, citations, chat history, or source previews
- Private GitHub repository OAuth/token access
- A distributed queue/retry worker system; current background tasks execute in the API process

Phase 4B adds configurable embedding generation behind a provider interface. See [PHASE_4B.md](PHASE_4B.md).
