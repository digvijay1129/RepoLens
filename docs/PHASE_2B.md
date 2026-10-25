# Phase 2B — Database operational verification and hardening

## Goal

Verify the Phase 2A PostgreSQL schema more deeply and improve the developer/operator workflow before adding repository API routes.

## Improvements

- Add a read-only schema-check CLI: `python -m app.db.schema_check`
- Verify the deployed Alembic revision, required tables and columns, primary/unique/check/foreign-key constraints, and expected indexes.
- Ensure malformed/incomplete PostgreSQL URLs fail with a safe configuration message.
- Add request-session tests confirming cleanup always happens and failed requests roll back the session before it closes.
- Expand database constraint tests for lowercase identity, supported indexing states, and non-negative retry counts.
- Add an opt-in read-only integration test against a migrated PostgreSQL database.
- Run PostgreSQL on the GitHub Actions runner without Docker, apply the migration, execute the integration check, and verify the live schema in CI.
- Keep frontend tests and the production build in the same workflow.

## Schema verification command

Run from `backend/` after configuring `.env` and applying migrations:

```powershell
alembic upgrade head
python -m app.db.schema_check
```

The command is read-only. A successful run reports the current migration revision and required application tables. If the schema is incomplete or the revision differs from the code's Alembic head, it lists the detected issues and exits non-zero. It does not print the database URL or password.

## Run tests

Backend unit tests (no PostgreSQL required for these):

```powershell
cd backend
pytest
```

To also run the live PostgreSQL integration test against a dedicated, already-migrated local test database:

```powershell
$env:REPOLENS_TEST_DATABASE_URL="postgresql+psycopg://repolens_user:YOUR_PASSWORD@localhost:5432/repolens"
pytest
```

Use a test database, not a production database. The integration test only executes `SELECT 1` and reads schema metadata, but still requires a valid connection and migration.

Frontend verification, from a second terminal:

```powershell
cd frontend
npm test
npm run build
```

## CI behavior

The backend CI job starts the runner's installed PostgreSQL service (not Docker), creates an isolated CI database with a randomly generated password, applies Alembic migrations, runs unit and live-PostgreSQL tests, and invokes the schema verifier. The CI password is generated at runtime and not stored in the repository. Migration SQL is also rendered offline to ensure the migration can be generated without opening a connection.

## Acceptance checklist

- [ ] Backend unit tests pass.
- [ ] Local live PostgreSQL migration and schema-check command pass.
- [ ] The optional integration test passes when `REPOLENS_TEST_DATABASE_URL` is set.
- [ ] Readiness returns HTTP 503 when the database is unavailable without leaking connection details.
- [ ] Frontend unit tests and production build still pass.
- [ ] GitHub Actions completes successfully for this branch.
- [ ] No `.env`, real password, tokens, private data, or credentials are committed.

## Not included

This phase does not add repository CRUD APIs, authentication, GitHub fetching, code chunks, pgvector extension setup, embedding jobs, RAG, LLM chat, or Docker.

Phase 3 should begin only after the live PostgreSQL checks have passed and the pull request has been reviewed.
