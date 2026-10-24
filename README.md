# RepoLens

**GitHub Codebase Intelligence Assistant** — a developer workspace for exploring repositories and asking code questions with evidence-backed RAG answers.

> Current milestone: Phase 1A — foundation and interface shell. Repository ingestion, PostgreSQL/pgvector, embeddings, and LLM chat come in later verified phases.

## Stack

- **Frontend:** React, Vite, JavaScript (JSX), CSS — no TypeScript
- **Backend:** Python 3.12+, FastAPI, Pydantic Settings
- **Planned data layer:** PostgreSQL + pgvector
- **Planned integrations:** GitHub REST API, embedding API, LLM API
- **Constraints:** no Docker and no model training

## Layout

- `backend/` — FastAPI application and automated tests
- `frontend/` — React application using JavaScript and Vite
- `docs/PHASE_1.md` — setup, scope, and verification checklist

## Prerequisites

Install Python 3.12+, Node.js 20+ with npm, Git, and (recommended) VS Code. PostgreSQL is not required until Phase 2.

## Run locally

### Backend

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

### Frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

On Windows use `Copy-Item .env.example .env` instead of `cp`. Open the local URL printed by Vite (normally http://localhost:5173).

## Tests

From the repository root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

On macOS/Linux activate with `source .venv/bin/activate`.

## Roadmap

- [x] Phase 1A: baseline, FastAPI health endpoints, tests, responsive React JavaScript interface
- [ ] Phase 1B: refine and verify foundation based on Phase 1A feedback
- [ ] Phase 2: PostgreSQL schema, SQLAlchemy, Alembic migrations, data isolation
- [ ] Phase 3: safe GitHub repository connection and browsing
- [ ] Phase 4: source parsing, chunking, indexing jobs, and embeddings
- [ ] Phase 5: hybrid retrieval with PostgreSQL full-text search and pgvector
- [ ] Phase 6: grounded LLM chat with source citations
- [ ] Phase 7: complete product workflows and UI integration
- [ ] Phase 8: security hardening, evaluation, CI, and deployment

## Security

Never commit `.env`, API keys, tokens, database passwords, private source, or user data. Downloaded repository files must be treated as untrusted input and never executed. Connect/chat controls in Phase 1A are previews: no repository is fetched, no prompt is stored, and no LLM is called yet.

See [Phase 1 instructions](docs/PHASE_1.md) for setup and verification.
