# Phase 2A — PostgreSQL persistence foundation

Phase 2A introduced SQLAlchemy, PostgreSQL connectivity, core persistence models, the initial Alembic migration, and a database-aware readiness endpoint.

Tables:
- `users`: a workspace owner identity (authentication remains a later phase).
- `repositories`: owner ID, GitHub repository metadata, indexing status, commit SHA and timestamps.
- `indexing_jobs`: owner/repository IDs, state, attempt count and timestamps.

The database schema includes unique constraints, check constraints, indexes, foreign keys, and a composite repository-owner relationship so a job must belong to the same user as its repository.

To configure a local PostgreSQL database, set `DATABASE_URL` in `backend/.env`, then run:

```powershell
cd backend
alembic upgrade head
alembic current
```

Phase 2B adds live PostgreSQL CI, schema verification, and database-session hardening. See [Phase 2B documentation](PHASE_2B.md).

This schema is only the persistence foundation. It does not yet enable repository CRUD endpoints, authentication, GitHub API calls, code chunking, pgvector embeddings, RAG or LLM chat.
