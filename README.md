# RepoLens

**GitHub Codebase Intelligence Assistant** — a developer workspace for exploring repositories and asking code questions with evidence-backed answers using retrieval-augmented generation (RAG).

> Current milestone: Phase 1B — foundation hardening, accessible repository URL validation, and frontend test coverage. GitHub ingestion, PostgreSQL/pgvector, embeddings, and LLM chat are added in later verified phases.

## Technology stack

- **Frontend:** React, Vite, JavaScript (JSX), CSS — no TypeScript
- **Backend:** Python 3.12+, FastAPI, Pydantic Settings
- **Planned data layer:** PostgreSQL + pgvector
- **Planned integrations:** GitHub REST API, embedding API, LLM API
- **Constraints:** no Docker and no model training

## Repository layout

- `backend/` — FastAPI application and backend tests
- `frontend/` — React app, URL validation helper, and frontend tests
- `docs/PHASE_1.md` — original foundation scope
- `docs/PHASE_1B.md` — current improvements and verification steps

## Prerequisites

Install Python 3.12+, Node.js 22.12+ with npm, and Git. VS Code is recommended. PostgreSQL is not required until Phase 2.

## Run locally

### 1. Start the backend

Windows PowerShell:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

macOS/Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Backend URLs: [API docs](http://127.0.0.1:8000/docs), [liveness](http://127.0.0.1:8000/api/v1/health/live), [readiness](http://127.0.0.1:8000/api/v1/health/ready).

### 2. Start the frontend

Open a second terminal from the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open the local URL printed by Vite (normally http://localhost:5173). In macOS/Linux, use `cp .env.example .env` instead of `Copy-Item`.

## Run tests

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

Frontend (from a separate terminal):

```powershell
cd frontend
npm test
```

Use `npm run test:watch` while developing UI changes. The frontend suite covers GitHub URL normalization, dangerous/lookalike URL rejection, dashboard state, modal keyboard behavior, and explicit preview-mode messaging.

## Roadmap

- [x] Phase 1A: baseline, FastAPI health endpoints, tests, responsive React JavaScript interface
- [x] Phase 1B implementation: accessible URL validation and frontend test coverage (verify CI and review before advancing)
- [ ] Phase 2: PostgreSQL schema, SQLAlchemy, Alembic migrations, data isolation
- [ ] Phase 3: safe GitHub repository connection and browsing
- [ ] Phase 4: source parsing, chunking, indexing jobs, and embeddings
- [ ] Phase 5: hybrid retrieval using PostgreSQL full-text search and pgvector
- [ ] Phase 6: grounded LLM chat with source citations
- [ ] Phase 7: complete product workflows and UI integration
- [ ] Phase 8: security hardening, retrieval evaluation, CI, and deployment

## Security notes

Never commit `.env`, API keys, tokens, database passwords, private source, or user data. Repository URLs are only format-validated during Phase 1B: no GitHub content is fetched or stored. Downloaded repository files will be treated as untrusted input and never executed. Ask/repository controls are not presented as working integrations until their phases are implemented.

See [Phase 1B instructions](docs/PHASE_1B.md) for scope and verification.
