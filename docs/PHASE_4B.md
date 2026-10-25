# Phase 4B — Configurable embeddings and versioned vector storage

## Scope

Phase 4B adds an opt-in embeddings layer on top of the Phase 4A source chunks. It creates real numeric embeddings through a configurable OpenAI-compatible HTTP API, persists versioned vectors in PostgreSQL, and exposes owner-scoped jobs with progress. It does not yet add semantic nearest-neighbor search or LLM chat; those are Phase 5 and Phase 6.

## Configuration

Copy the current backend example into `backend/.env`. These settings are optional and do not affect source indexing:

```dotenv
EMBEDDINGS_ENABLED=false
EMBEDDINGS_PROVIDER=openai_compatible
EMBEDDINGS_API_KEY=
EMBEDDINGS_BASE_URL=https://api.openai.com/v1
EMBEDDINGS_MODEL=text-embedding-3-small
EMBEDDINGS_DIMENSIONS=1536
EMBEDDINGS_BATCH_SIZE=32
EMBEDDINGS_TIMEOUT_SECONDS=30
```

To enable generation, set `EMBEDDINGS_ENABLED=true` and supply the provider's API key. The key is only read by the backend and is never returned in API responses. Remote endpoints require HTTPS; plain HTTP is allowed only for localhost during local development. The default model/dimension values are examples and must match the embedding model selected from your provider.

Without this configuration, source retrieval and chunk persistence continue to work. The **Generate embeddings** API returns a clear configuration error instead of fabricating vectors or preventing source indexing.

## What is implemented

- A provider interface with an OpenAI-compatible `POST /embeddings` contract, configurable endpoint, secret key, model, dimensions, batch size and timeout.
- Strict validation of provider response count/order, indexes, vector dimensions, numeric values and finite floats.
- Sanitized failures for credential rejection, rate limits, provider outages, timeouts, and invalid response payloads.
- Persistent `repository_chunk_embeddings` table. Each vector stores chunk ID, owner/repository/commit, provider, model, dimensions, source content hash, numeric vector (JSON), and creation time.
- A uniqueness key per chunk/provider/model/dimension. Different model versions can coexist for the same source snapshot without mixing incompatible vector spaces.
- `indexing_jobs.job_type` distinguishes source indexing from embedding jobs, and embedding progress includes provider/model/dimension metadata.
- `repositories.embedding_status` reports pending, embedding, embedded or failed, plus the active provider/model/dimensions and last successful embed time.
- The Code Explorer offers **Generate embeddings** after successful source indexing and displays job progress and active embedding metadata.
- Retried jobs reuse already-complete embeddings for the same chunk content hash and configuration.
- Failed model changes do not replace the previously active embedding configuration. Successfully generated rows for a new configuration may be reused on retry, but are not marked as active until the entire job completes.
- Source re-indexing resets the active embedding status when a new commit becomes the completed snapshot; old embedding rows are cascade-deleted with their superseded chunks.

## API

- `POST /api/v1/repositories/saved/{repository_id}/embeddings` — queues a configured embedding job for the current indexed snapshot.
- `GET /api/v1/repositories/saved/{repository_id}/jobs/{job_id}` — returns owner-scoped progress for either job type.

Both endpoints require an authenticated owner. The server verifies repository ownership before returning or starting work.

## Storage decision

Vectors are stored as JSON arrays in this phase so local setup does not need a PostgreSQL extension. This is durable and suitable for testing metadata flow, but it is not an efficient similarity-search index. Phase 5 will introduce pgvector and indexed distance search, preserving provider/model/dimension metadata and applying a migration strategy for stored vectors.

## Migration and tests

The new Alembic revision is `20261025_0005`. Apply it without recreating the database:

```powershell
cd backend
alembic upgrade head
alembic current
python -m app.db.schema_check
pytest
```

Frontend verification:

```powershell
cd frontend
npm test
npm run build
```

## Current boundaries

- Provider API calls can incur cost. Embedding generation is explicit, opt-in, and user-triggered. Eligible source chunks are sent to the configured external provider, so review its data-retention/privacy terms and only index code you are authorized to share. The backend keeps the provider API key server-side.
- Provider/model token limits vary. The current chunks are bounded to 4,000 characters; provider errors are surfaced with safe messages.
- The worker is an in-process FastAPI background task. A distributed queue, rate limiting, retry backoff and billing quotas belong in later production-hardening work.
- No pgvector extension or similarity query is added yet. No RAG answer generation or LLM chat is added yet.
- Public GitHub repositories only; no private GitHub tokens, OAuth, Docker, TypeScript, or model training.

## Verification checklist

- [ ] Source indexing still works with embeddings disabled and no embedding key configured.
- [ ] With a valid key/model, the embedding job stores numeric vectors matching the configured dimensions.
- [ ] Same-commit re-run skips already stored vectors for the same provider/model/dimensions/content hash.
- [ ] A provider error produces a failed job without exposing credentials or deleting the previously active model vectors.
- [ ] A different user cannot create/read an embedding job for another user's repository.
- [ ] Migration, live PostgreSQL schema check, backend tests, frontend tests and production build pass.
