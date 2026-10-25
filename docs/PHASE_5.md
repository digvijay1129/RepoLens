# Phase 5 — pgvector semantic search, hybrid retrieval, and source citations

## Scope

Phase 5 connects indexed source chunks and embeddings to retrieval APIs. Search returns source-grounded chunks from a single immutable commit with exact GitHub file/line citations. It does not generate an LLM answer; that remains Phase 6.

## Retrieval modes

- **Keyword:** PostgreSQL full-text search using the `simple` configuration and a GIN expression index. It can be used without embeddings.
- **Semantic:** embeds the search query using the repository's active provider/model and orders the current source snapshot by pgvector cosine distance.
- **Hybrid:** combines semantic and keyword rankings with reciprocal-rank fusion (RRF), which lets exact identifiers and conceptually related code both contribute without mixing incompatible raw score scales.

PostgreSQL applies owner, repository, commit, provider, model, dimension and content-hash filters before returning eligible vector matches. The service never searches another user's source, another repository, stale commit snapshots, or embeddings whose content hash no longer matches their source chunk.

## API

`POST /api/v1/repositories/saved/{repository_id}/search`

Example:

```json
{
  "query": "How is JWT authentication validated?",
  "mode": "hybrid",
  "limit": 8
}
```

Modes are `keyword`, `semantic`, and `hybrid`. Limit must be between 1 and 20; query length must be 2–500 characters. The endpoint requires authentication and repository ownership.

Each result includes the file path, language, symbol names, original source line range, chunk snippet, normalized ranking score, match type(s), indexed commit SHA and a GitHub link targeting the exact cited lines.

## PostgreSQL / pgvector migration

Migration `20261025_0006`:
- Converts persisted JSON vectors to the PostgreSQL `vector` type.
- Creates the `vector` extension if it is already installed on the server. The extension's server package is required first; a database administrator may need to create the extension before applying migrations if the application role lacks extension privileges.
- Adds the PostgreSQL GIN index `ix_repository_chunks_fts_simple` for full-text search.

For GitHub Actions, CI installs the pgvector package for the preinstalled PostgreSQL 18 server, creates the extension as the PostgreSQL administrator, and then applies Alembic migrations. No Docker is used.

## Local setup

Install the pgvector server extension for the PostgreSQL version you run, then create the extension in the RepoLens database using a PostgreSQL administrator account:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Then, from `backend/`:

```powershell
alembic upgrade head
alembic current
python -m app.db.schema_check
pytest
```

Migration `20261025_0006` expects the extension to be available. Existing JSON embeddings are converted in place; do not delete or recreate the database.

Semantic and hybrid search require the currently configured provider/model/dimensions to match the repository's active embedding configuration. If you switch models, generate embeddings for the new configuration before searching.

## UI

The Code Explorer contains a **Search this codebase** panel with:
- Query input
- Hybrid, semantic, and keyword modes
- Progress/error handling
- Ranked source snippets, function/class names, score, match type, commit short SHA and a one-click GitHub citation link

Keyword search works after source indexing. Semantic/hybrid controls are enabled once the current snapshot has successful embeddings.

## Indexing strategy and limits

Semantic ranking currently performs exact cosine-distance ordering over rows filtered to the current repository, owner, commit, provider, model and vector dimensions. This avoids an approximate index accidentally mixing incompatible dimensions or embedding spaces. The GIN index accelerates keyword retrieval; filtered exact vector ranking is appropriate for the current bounded repository indexing limits. If corpus sizes grow, benchmark and introduce model/dimension-specific HNSW or IVFFlat indexes rather than one unfiltered approximate index.

## Tests

CI verifies:
- Migration to revision `20261025_0006`, native vector column and full-text index in live PostgreSQL.
- Keyword, semantic and hybrid ordering through service-level tests.
- Query embeddings via a mocked provider, correct model/dimension guards and source citation links.
- Owner, repository and commit scoping; unindexed repositories and model mismatches are rejected.
- API and frontend search flows, plus the production UI build.

## Not included

- LLM-generated natural-language answers and multi-turn chat (Phase 6)
- Code execution or repository imports
- Private GitHub repository support
- Distributed background queue, billing controls or rate-limiting
- Docker or TypeScript
