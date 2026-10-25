# Phase 2A — PostgreSQL persistence foundation

## Goal

Add the persistence foundation before exposing repository CRUD APIs. This phase introduces SQLAlchemy, Alembic, PostgreSQL connectivity, an initial schema, and database-aware readiness.

## Included

- SQLAlchemy 2 declarative base and predictable constraint naming
- PostgreSQL psycopg 3 driver, pooled engine, and request-scoped session dependency
- DATABASE_URL validation and normalization to `postgresql+psycopg://`
- Initial schema for users, repositories, and indexing jobs
- Ownership constraints: indexing jobs must match the repository owner
- Unique repository ownership/name constraint and status/attempt-count checks
- Alembic environment and a reversible initial migration
- Readiness check using `SELECT 1`; safe HTTP 503 if the database is missing or unavailable
- SQLite schema/model tests and CI generation of PostgreSQL migration SQL

## Tables

### `users`
Workspace owner identity: UUID primary key, normalized email, optional display name, and timestamps. Authentication is deferred.

### `repositories`
Owner ID, GitHub owner/name, canonical full name and URL, default branch, indexed commit SHA, indexing status, timestamps, and last indexed time. Duplicate normalized repositories for the same user are rejected.

### `indexing_jobs`
Owner and repository IDs, status, attempt count, bounded error text, timestamps, and indexes for owner/status history. A composite foreign key enforces that a job's user matches its repository's user.

## Not included yet

- pgvector extension or embedding columns
- GitHub API calls, OAuth, repository downloads, or private-repository access
- Code-chunk persistence or worker execution
- CRUD routes, authentication, or request-level user authorization
- RAG retrieval, LLM calls, chat persistence, Docker, or production deployment

Models are data-layer foundations only. Do not expose them in public routes until identity and authorization are implemented.

## Local setup

1. Install PostgreSQL 16+ and start its service.
2. Create a local database and user with pgAdmin or `psql` (example SQL is in the README).
3. From `backend/`, create and activate the Python virtual environment, then run `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and configure `DATABASE_URL`.
5. Run `alembic upgrade head`, then `alembic current`.
6. Run `uvicorn app.main:app --reload`.
7. Confirm readiness returns `{"status":"ready","database":"ok"}` only when a database connection succeeds.

## Tests and migration generation

From `backend/`:

```powershell
pytest
alembic upgrade head --sql
```

`alembic upgrade head --sql` generates migration SQL without connecting or applying it. CI verifies this offline generation. Local `alembic upgrade head` is required to test connectivity and apply the schema to PostgreSQL.

## Acceptance checklist

- [ ] Backend tests pass.
- [ ] Frontend tests and the production build pass.
- [ ] Alembic can render PostgreSQL migration SQL.
- [ ] Locally, `alembic upgrade head` creates all three tables and constraints.
- [ ] Liveness remains healthy without a database.
- [ ] Readiness returns HTTP 503 when `DATABASE_URL` is absent or PostgreSQL is unreachable, without leaking secrets.
- [ ] Readiness reports database OK when PostgreSQL is reachable.
- [ ] No `.env`, passwords, or tokens are committed.

Phase 2A implements the schema layer only; it does not enable persisted repository APIs.
