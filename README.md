# RepoLens

**GitHub Codebase Intelligence Assistant** — a developer workspace for exploring repositories and asking code questions with evidence-backed RAG answers.

> Current milestone: Phase 2A — PostgreSQL persistence foundation, migrations, and database-aware readiness. GitHub ingestion, embeddings, vector retrieval, and LLM chat are later phases.

## Stack

- Frontend: React, Vite, JavaScript/JSX, CSS — no TypeScript
- Backend: Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, psycopg 3
- Database: PostgreSQL 16+
- Planned vector retrieval: pgvector, introduced with the indexing/retrieval phases
- Constraints: no Docker and no model training

## Prerequisites

Install Python 3.12+, Node.js 22.12+ with npm, Git, and PostgreSQL 16+. VS Code is recommended.

## Create a local database

Use pgAdmin or `psql`. Example SQL, run as your local PostgreSQL administrator:

```sql
CREATE USER repolens_user WITH PASSWORD 'replace_with_a_strong_local_password';
CREATE DATABASE repolens OWNER repolens_user;
```

Skip creation if your local user/database already exists; configure the existing values instead.

## Backend setup

Windows PowerShell, from the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and replace the placeholder in `DATABASE_URL` with your actual local connection URL. Keep this file private; `.gitignore` excludes it. URL-encode special characters in the database password.

Apply and inspect the migration from the backend directory:

```powershell
alembic upgrade head
alembic current
```

Start the API:

```powershell
uvicorn app.main:app --reload
```

Endpoints:
- API docs: http://127.0.0.1:8000/docs
- Liveness: http://127.0.0.1:8000/api/v1/health/live
- Readiness: http://127.0.0.1:8000/api/v1/health/ready

Liveness does not require a database. Readiness returns HTTP 503 if PostgreSQL is missing or unreachable, without returning connection details.

## Frontend setup

Open a second terminal at the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm test
npm run build
npm run dev
```

Open the URL printed by Vite (normally http://localhost:5173).

## Run backend tests

With the backend virtual environment active:

```powershell
cd backend
pytest
```

Schema/model tests use in-memory SQLite. CI also renders the Alembic migration in PostgreSQL dialect without a database server; run `alembic upgrade head` locally to test actual PostgreSQL connectivity and apply the schema.

## Roadmap

- [x] Phase 1A: foundation and React JavaScript interface
- [x] Phase 1B: URL validation, modal accessibility, frontend tests
- [x] Phase 2A implementation: SQLAlchemy models, Alembic migration, session setup, DB readiness
- [ ] Phase 2B: verify real PostgreSQL migration and harden operational setup
- [ ] Phase 3: GitHub repository connection and browsing
- [ ] Phase 4: code chunking, indexing jobs, and embeddings
- [ ] Phase 5: hybrid retrieval with PostgreSQL full-text search and pgvector
- [ ] Phase 6: grounded LLM chat and citations
- [ ] Phase 7: complete product workflows and UI integration
- [ ] Phase 8: security, evaluation, CI, and deployment

## Security

Never commit `.env`, API keys, tokens, database passwords, private source, or user data. The URL form validates format only; it does not fetch repository files. Authentication is not implemented yet, so user IDs in the database are an ownership foundation and must not be treated as completed API authorization.

See [Phase 2A instructions](docs/PHASE_2A.md).
