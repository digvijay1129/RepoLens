# RepoLens

**GitHub Codebase Intelligence Assistant** — a developer workspace for exploring repositories and asking code questions with evidence-backed answers using retrieval-augmented generation (RAG).

> Current milestone: Phase 3A — real public GitHub repository inspection and directory browsing. Persistent repository management, indexing, embeddings, vector retrieval, and LLM chat are added in later phases.

## Stack

- Frontend: React, Vite, JavaScript/JSX, CSS — no TypeScript
- Backend: Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, HTTPX
- Database: PostgreSQL 16+
- Planned vector retrieval: pgvector, introduced with indexing/retrieval phases
- GitHub integration: unauthenticated public GitHub REST API
- Constraints: no Docker and no model training

## Prerequisites

Install Python 3.12+, Node.js 22.12+ with npm, Git, and PostgreSQL 16+. VS Code is recommended.

## First-time setup

### 1. Create a local database

Use pgAdmin or psql. Example SQL, run as your local PostgreSQL administrator:

```sql
CREATE USER repolens_user WITH PASSWORD 'replace_with_a_strong_local_password';
CREATE DATABASE repolens OWNER repolens_user;
```

### 2. Configure and start the backend

Windows PowerShell, from the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit backend/.env and replace the placeholder DATABASE_URL with your local PostgreSQL URL. Keep the actual .env private; .gitignore excludes it.

Apply migrations and check the schema:

```powershell
alembic upgrade head
alembic current
python -m app.db.schema_check
```

Start the API:

```powershell
uvicorn app.main:app --reload
```

Backend URLs:
- API docs: http://127.0.0.1:8000/docs
- Liveness: http://127.0.0.1:8000/api/v1/health/live
- Readiness: http://127.0.0.1:8000/api/v1/health/ready

### 3. Start the frontend

Open a second terminal from the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm test
npm run build
npm run dev
```

Open the URL printed by Vite (normally http://localhost:5173).

## Run tests

Backend (with its virtual environment active):

```powershell
cd backend
pytest
```

Frontend:

```powershell
cd frontend
npm test
npm run build
```

GitHub Actions also applies the Alembic migrations to a disposable PostgreSQL database and verifies the live schema.

## Phase 3A — public GitHub repository browsing

1. Open RepoLens and choose **Connect repository**.
2. Paste a public repository URL such as https://github.com/digvijay1129/RepoLens.
3. RepoLens validates the URL in the browser and the FastAPI backend independently validates it.
4. The backend fetches curated metadata from the fixed GitHub API host.
5. The Code explorer lists the live directory entries for the default branch. Select a folder to browse deeper; clicking a file opens its GitHub page.

### Security and limits

- Only HTTPS URLs on the exact github.com host are accepted.
- The backend uses a fixed api.github.com base URL and never accepts a caller-supplied upstream host.
- No access token or GitHub login is sent; only public repositories are supported in this phase.
- Responses are curated to avoid passing through arbitrary GitHub payload fields.
- Directory paths and refs are length-limited and validated; GitHub errors/rate limits are converted to safe messages.
- This phase lists file metadata but does not download source contents, persist repository connections, or execute repository code.
- Repository selections live only in browser memory and disappear when the page is reloaded. PostgreSQL persistence requires identity/authentication first.

See docs/PHASE_3A.md for implementation details and acceptance checks. Previous phases are documented in docs/PHASE_1B.md, docs/PHASE_2A.md, and docs/PHASE_2B.md.

## Roadmap

- [x] Phase 1A: application foundation and responsive React JavaScript UI
- [x] Phase 1B: URL validation, modal accessibility, frontend tests
- [x] Phase 2A: SQLAlchemy models and initial PostgreSQL migration
- [x] Phase 2B: corrective migration, live schema verification, and session hardening
- [x] Phase 3A implementation: public metadata inspection, directory browsing, safe errors, and API/UI tests
- [ ] Phase 3B: branch selection, repository persistence, and authenticated ownership
- [ ] Phase 4: code parsing, chunking, indexing jobs, and embeddings
- [ ] Phase 5: hybrid retrieval using PostgreSQL full-text search and pgvector
- [ ] Phase 6: grounded LLM chat and citations
- [ ] Phase 7: complete product workflows
- [ ] Phase 8: security hardening, evaluation, deployment, and final packaging

## Security

Never commit .env, API keys, tokens, database passwords, private source, or user data. Repository URLs are not treated as proof of authentication. Until identity is implemented, repository metadata is session-only and no repository CRUD route is exposed.
