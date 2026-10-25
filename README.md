# RepoLens

**RepoLens is a GitHub Codebase Intelligence Assistant** that helps developers explore, index, search, and ask questions about public GitHub repositories. It combines a React workspace, FastAPI backend, PostgreSQL, pgvector, hybrid retrieval, and citation-grounded RAG chat.

[Repository](https://github.com/digvijay1129/RepoLens) · [Issues](https://github.com/digvijay1129/RepoLens/issues) · [Security policy](SECURITY.md)

## Highlights

- **Repository workspace:** connect public GitHub repositories, browse directories, and switch branches.
- **Safe source indexing:** bounded retrieval of allowlisted text files, deterministic overlapping chunks, commit snapshots, line ranges, and content hashes. Source files are never executed.
- **Hybrid code search:** PostgreSQL full-text keyword search plus pgvector cosine similarity, with reciprocal-rank fusion and source-line references.
- **AI codebase Q&A:** optional OpenRouter-compatible LLM integration generates answers grounded in retrieved source chunks and links citations back to files and lines.
- **Persistent workspace:** PostgreSQL stores accounts, saved repositories, indexing/embedding jobs, chunk metadata, and conversation history.
- **Evaluation:** offline retrieval metrics include Recall@k, MRR, nDCG@k, citation validity, support precision, and coverage.
- **Quality checks:** backend test suite, live PostgreSQL migration/schema verification, frontend unit tests, production build, and source-only release archive validation.

## Architecture

```text
React + Vite + Tailwind CSS (JavaScript / JSX)
                 |
                 | REST API (/api/v1)
                 v
          FastAPI application
       /          |           \
 Auth/JWT   GitHub API     RAG services
                  |       /      |      \
             Public repo  Index  Search  LLM
                          |      |
                          v      v
                    PostgreSQL + pgvector
                   migrations / persistent data
```

### Technology stack

| Layer | Technologies |
|---|---|
| Frontend | React, Vite, JavaScript/JSX, Tailwind CSS, Vitest |
| Backend | Python, FastAPI, Pydantic Settings, SQLAlchemy 2, Alembic |
| Data | PostgreSQL 16+, pgvector, PostgreSQL full-text search |
| Retrieval and AI | Source chunking, vector embeddings, hybrid retrieval, reciprocal-rank fusion, RAG chat, OpenRouter-compatible APIs |
| Identity and security | Argon2 password hashing, signed JWT access tokens, owner-scoped database queries, security headers, trusted-host configuration |
| Testing and delivery | pytest, Vitest, production frontend build, GitHub Actions CI, source release ZIP validation |

RepoLens does not use Docker for local setup, does not train a model, and currently supports public GitHub repositories only.

## Features and workflow

1. Register or sign in.
2. Connect a public GitHub repository by URL.
3. Browse files and folders and select a branch.
4. Index bounded source files from a specific commit snapshot.
5. Generate embeddings when an embedding provider is configured.
6. Run keyword, semantic, or hybrid code search.
7. Ask RepoLens a question about the codebase; retrieved context and citations are saved in the workspace.
8. Review prior conversations and run the offline retrieval/citation evaluation harness.

Keyword search can be used without an embedding or LLM API key. Semantic/hybrid search requires generated embeddings. AI chat requires a configured LLM provider and can incur provider costs.

## Requirements

- Python 3.12 or newer
- Node.js 22.12 or newer and npm
- PostgreSQL 16 or newer
- The PostgreSQL vector extension (pgvector)
- Git

VS Code is recommended for local development.

## Local setup (Windows PowerShell)

### 1. Create the PostgreSQL database

Open pgAdmin or psql as a local PostgreSQL administrator and run the following, changing the password to a strong local-only value:

```sql
CREATE USER repolens_user WITH PASSWORD 'replace_with_a_strong_local_password';
CREATE DATABASE repolens OWNER repolens_user;
```

Install the pgvector extension for your PostgreSQL installation and ensure it is available to the database. Then enable it:

```sql
\c repolens
CREATE EXTENSION IF NOT EXISTS vector;
```

Skip the user/database creation if they already exist. Do not use production credentials for local development.

### 2. Configure and start the backend

From the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit backend/.env and set DATABASE_URL. Generate a private JWT signing secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the generated value as JWT_SECRET_KEY (minimum 32 bytes). Keep backend/.env private and never commit it.

Apply and verify database migrations:

```powershell
alembic upgrade head
alembic current
python -m app.db.schema_check
```

Start the API:

```powershell
uvicorn app.main:app --reload
```

- API documentation: http://127.0.0.1:8000/docs
- Liveness: http://127.0.0.1:8000/api/v1/health/live
- Readiness: http://127.0.0.1:8000/api/v1/health/ready

### 3. Configure and start the frontend

Open a second terminal at the repository root:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm test
npm run build
npm run dev
```

Open the local URL printed by Vite (usually http://localhost:5173). The frontend API base URL defaults to http://127.0.0.1:8000 and can be overridden with VITE_API_BASE_URL.

## Optional AI provider configuration

To enable OpenRouter chat, set the following in backend/.env:

```dotenv
OPENROUTER_API_KEY=your_private_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_CHAT_MODEL=openai/gpt-5.6-luna
OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small
OPENROUTER_HTTP_REFERER=http://localhost:5173
OPENROUTER_APP_TITLE=RepoLens
LLM_ENABLED=true
EMBEDDINGS_ENABLED=true
EMBEDDINGS_DIMENSIONS=1536
```

Configure the embedding provider values to match the embedding API you intend to use. Keep every API key in backend-only environment variables—never put it in frontend/.env or commit it. Set EMBEDDINGS_ENABLED=true only when generating embeddings; source indexing and keyword retrieval do not require embeddings. Provider calls may incur costs, and code excerpts retrieved for chat are sent to the configured provider.

The checked-in backend/.env.example documents the supported local settings and defaults. Change model identifiers only to models supported by your selected provider.

## API overview

Routes are versioned under /api/v1. Use the automatically generated API docs in development for request and response schemas.

### Health
- GET /api/v1/health/live
- GET /api/v1/health/ready

### Authentication
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- GET /api/v1/auth/me (bearer token required)

### Repository workspace and code intelligence
- POST /api/v1/repositories/inspect — preview public repository metadata
- POST /api/v1/repositories/saved — save a repository to the current user's workspace
- GET /api/v1/repositories/saved — list the current user's repositories
- DELETE /api/v1/repositories/saved/{repository_id} — remove an owned repository
- GET /api/v1/repositories/saved/{repository_id}/branches — list branches
- PATCH /api/v1/repositories/saved/{repository_id}/branch — set the selected branch
- POST /api/v1/repositories/saved/{repository_id}/index — queue source indexing
- GET /api/v1/repositories/saved/{repository_id}/jobs/{job_id} — inspect indexing/embedding progress
- POST /api/v1/repositories/saved/{repository_id}/embeddings — generate configured embeddings
- POST /api/v1/repositories/saved/{repository_id}/search — keyword, semantic, or hybrid search
- POST /api/v1/repositories/saved/{repository_id}/chat — ask a grounded codebase question
- GET /api/v1/repositories/saved/{repository_id}/conversations and GET /api/v1/repositories/saved/{repository_id}/conversations/{conversation_id} — saved chat history
- GET /api/v1/repositories/{owner}/{repository}/contents — browse public directory contents with optional path and ref

Workspace data access is scoped to the authenticated user; consult /docs for request/response schemas and exact validation rules.

## Tests and CI

Run backend tests from an activated backend environment:

```powershell
cd backend
pytest
```

Run frontend checks:

```powershell
cd frontend
npm test
npm run build
```

GitHub Actions runs backend tests and a live PostgreSQL schema check using a PostgreSQL service image with pgvector. It also runs frontend tests and a production build. Once both suites pass, CI builds and validates a source-only release ZIP. The workflow does not modify the runner's host package repositories.

## Repository layout

```text
.github/workflows/ci.yml        Continuous integration and release validation
backend/app/api/                Versioned REST API and request schemas
backend/app/core/               Application configuration and security settings
backend/app/db/                 Database session, metadata, and schema checker
backend/app/models/             SQLAlchemy data models
backend/app/services/           GitHub, indexing, embeddings, retrieval and RAG services
backend/app/evaluation/         Offline retrieval/citation evaluation
backend/migrations/             Versioned Alembic migrations
backend/tests/                  Backend unit and integration tests
frontend/src/components/        Reusable UI components
frontend/src/pages/              Workspace pages
frontend/src/lib/                API client and GitHub URL helpers
frontend/src/styles.css          Application styles
docs/                            Phase notes and deployment/security documentation
scripts/package_release.py       Source-only ZIP builder and validator
```

## Security and limitations

- Passwords are hashed with Argon2; plaintext passwords are not stored.
- Signed JWT access tokens use issuer, audience, and expiry claims. The browser stores the token in sessionStorage for the current tab/session.
- Saved repository operations are scoped to the signed-in user's ID.
- Input repository URLs are restricted to HTTPS on the exact GitHub host; server-side public API calls use the fixed GitHub API origin.
- Only public repositories are supported; private-repository access and GitHub OAuth are not implemented.
- Source ingestion is bounded and uses allowlisted text-file handling; indexed code is not executed.
- Do not commit .env files, credentials, private code, or real user data.

Before public deployment, complete a security review and add production operations such as rate limiting, email verification and account recovery, secret management, monitoring, backups, TLS, and an appropriate deployment plan. Read [SECURITY.md](SECURITY.md) and [Phase 8 deployment notes](docs/PHASE_8.md).

## Retrieval evaluation

The example file backend/evaluation/examples/openrouter_rag_run.jsonl illustrates the expected JSONL input format with synthetic sample data. From backend/, run:

```powershell
python -m app.evaluation.evaluate --input evaluation/examples/openrouter_rag_run.jsonl --k 5 --output evaluation/report.json
```

The evaluation report includes Recall@k, MRR, nDCG@k, citation validity, support precision, and coverage. The sample is illustrative only; measure real performance with representative queries and human-reviewed relevance and citation labels.

## Project documentation

- [Phase 1 — Foundation](docs/PHASE_1.md)
- [Phase 1B — Frontend and URL validation](docs/PHASE_1B.md)
- [Phase 2A — Database foundation](docs/PHASE_2A.md)
- [Phase 2B — Live database and schema verification](docs/PHASE_2B.md)
- [Phase 3A — GitHub repository browsing](docs/PHASE_3A.md)
- [Phase 3B — Authentication and saved repositories](docs/PHASE_3B.md)
- [Phase 4A — Source indexing](docs/PHASE_4A.md)
- [Phase 4B — Embeddings](docs/PHASE_4B.md)
- [Phase 5 — Retrieval and citations](docs/PHASE_5.md)
- [Phase 6 — RAG chat and history](docs/PHASE_6.md)
- [Phase 7 — Provider integration and evaluation](docs/PHASE_7.md)
- [Phase 8 — Deployment and security](docs/PHASE_8.md)

## Current status

RepoLens implements the capabilities described above and includes automated tests and CI checks. Passing tests and schema validation are a useful baseline, not proof of production readiness. Validate the full setup with your own database and provider configuration before relying on it in a deployed environment.
