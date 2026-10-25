# RepoLens

**GitHub Codebase Intelligence Assistant** — a developer workspace for public GitHub repositories with source indexing, pgvector and keyword retrieval, hybrid search, and citation-grounded RAG chat.

## Current implementation

- React + Vite + JavaScript/JSX frontend (no TypeScript)
- Python + FastAPI backend
- PostgreSQL 16+, SQLAlchemy 2, and Alembic migrations
- Argon2 password hashing, short-lived signed JWT access tokens, authenticated workspace APIs
- Public GitHub REST API integration for repository metadata, branches, directory listings, and bounded source retrieval
- Persistent indexing jobs, source-safe file filtering, deterministic overlapping chunks, line references and content hashes
- Configurable OpenAI-compatible embedding provider, versioned vector storage metadata, retryable owner-scoped embedding jobs
- pgvector cosine-similarity retrieval, PostgreSQL full-text search, hybrid reciprocal-rank fusion, and file/line citations
- Persistent owner-scoped repository metadata and selected-branch preference
- OpenRouter chat and optional embeddings using a backend-only key
- Offline Recall@k, MRR, nDCG@k, and citation-quality evaluation
- Production configuration validation, trusted-host checks, security headers, and no-store API responses
- CI tests, live PostgreSQL migration verification, and production frontend build

No Docker and no model training are used.

## Prerequisites

Install Python 3.12+, Node.js 22.12+ with npm, Git, and PostgreSQL 16+. VS Code is recommended.

## Setup in VS Code (Windows PowerShell)

### 1. Create a local database

Use pgAdmin or psql, connected as your local PostgreSQL administrator:

```sql
CREATE USER repolens_user WITH PASSWORD 'replace_with_a_strong_local_password';
CREATE DATABASE repolens OWNER repolens_user;
```

Skip creation if you already have this database/user. Use a local development database, not production.

### 2. Configure the backend

From the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and set `DATABASE_URL` to your local PostgreSQL connection. Generate a private JWT signing secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the generated value into `JWT_SECRET_KEY=` in `backend/.env`. It must be at least 32 bytes. Do not reuse the example value, share the secret, or commit `.env`.

Apply the schema through the latest migration and verify it:

```powershell
alembic upgrade head
alembic current
python -m app.db.schema_check
```

Phase 3B adds Alembic revision `20261025_0003`. If the database is at Phase 2B revision `20261025_0002`, `alembic upgrade head` applies the additions without dropping tables or data.

Start the backend:

```powershell
uvicorn app.main:app --reload
```

- API docs: http://127.0.0.1:8000/docs
- Liveness: http://127.0.0.1:8000/api/v1/health/live
- Readiness: http://127.0.0.1:8000/api/v1/health/ready

### 3. Start the frontend

Open another terminal at the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm test
npm run build
npm run dev
```

Open the local URL printed by Vite (normally http://localhost:5173).

## Use RepoLens

1. Create an account with an email and a password of at least 12 characters, or sign in.
2. Select **Connect repository** and enter a public GitHub URL.
3. RepoLens validates the input, fetches metadata from GitHub's public API, and saves the repository to your authenticated PostgreSQL-backed workspace.
4. Open **Code explorer**. Use the branch selector to choose an available branch; the selection is saved.
5. Browse folders. File links open the current selected branch's file page on GitHub.
6. Click **Index source files** to queue an indexing job. The workspace shows progress, skipped files, chunk count, and the commit snapshot when indexing finishes.
7. To generate embeddings, set `EMBEDDINGS_ENABLED=true` and configure the backend-only provider values in `backend/.env`, then select **Generate embeddings** in Code Explorer. Embeddings are opt-in and are not required for source indexing.
8. Use **Search this codebase** to search your current indexed commit with keyword, semantic, or hybrid retrieval. Results include GitHub links to exact source line ranges.
9. Configure the optional OpenRouter LLM provider in `backend/.env` and use **Ask RepoLens** for grounded answers with file/line citations.

Repository metadata, branch preference, source chunks, embeddings, and saved conversations persist across sessions and are scoped to the signed-in user's ID. Indexing reads only bounded, allowlisted UTF-8 text files from public repositories, records file paths and line ranges, and never executes source code.

## OpenRouter configuration

Copy `backend/.env.example` to `backend/.env` and set `OPENROUTER_API_KEY` to your private OpenRouter key. The provided defaults are `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`, `OPENROUTER_CHAT_MODEL=openai/gpt-5.6-luna`, and `OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small`. Set `LLM_ENABLED=true` to enable chat. Set `EMBEDDINGS_ENABLED=true` only when you want to generate embeddings and use semantic/hybrid retrieval. Never expose the key in frontend configuration or commit `.env`.

## Security and production notes

Read [Phase 8 deployment and security notes](docs/PHASE_8.md) and [SECURITY.md](SECURITY.md) before hosting the service publicly. Production mode requires a strong JWT key, TLS for remote PostgreSQL, explicit HTTPS CORS origins, real trusted host names, and an HTTPS OpenRouter referer when configured. Interactive API documentation is disabled in production. This project still requires distributed rate limiting, account recovery/email verification, monitoring, and a separate security review before broad public launch.

## OpenRouter configuration

RepoLens can use one OpenRouter API key for chat and optional embeddings. Add these values to \`backend/.env\`:

\`\`\`dotenv
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_CHAT_MODEL=openai/gpt-5.6-luna
OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small
OPENROUTER_HTTP_REFERER=http://localhost:5173
OPENROUTER_APP_TITLE=RepoLens

LLM_ENABLED=true
LLM_MAX_RETRIES=2
EMBEDDINGS_ENABLED=true
EMBEDDINGS_DIMENSIONS=1536
\`\`\`

Embedding generation is optional for keyword-based RAG. Set \`EMBEDDINGS_ENABLED=true\` when you want to generate vectors and use semantic/hybrid retrieval. The OpenRouter key is backend-only; never commit \`backend/.env\` or place this key in frontend settings. Set \`OPENROUTER_HTTP_REFERER\` to your deployed app origin when hosting the project. Provider calls may incur cost, and retrieved repository excerpts are sent to the configured model provider.

## Offline retrieval evaluation

From the \`backend/\` folder, run the illustrative JSONL sample through the evaluation harness:

\`\`\`powershell
python -m app.evaluation.evaluate --input evaluation/examples/openrouter_rag_run.jsonl --k 5 --output evaluation/report.json
\`\`\`

The report includes Recall@k, MRR, nDCG@k, citation validity, support precision and coverage. The included data is synthetic and illustrates the schema only; use representative queries and human-reviewed relevance/citation labels to judge real retrieval quality.

## API endpoints

### Authentication

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me` (bearer token required)

### Repository workspace

- `POST /api/v1/repositories/saved` — inspect and persist a public repository for the current user
- `GET /api/v1/repositories/saved` — list current user's saved repositories
- `DELETE /api/v1/repositories/saved/{repository_id}` — remove only a record owned by the current user
- `GET /api/v1/repositories/saved/{repository_id}/branches` — list branches after checking ownership
- `PATCH /api/v1/repositories/saved/{repository_id}/branch` — validate and persist selected branch
- `POST /api/v1/repositories/saved/{repository_id}/index` — queue a safe source indexing job
- `GET /api/v1/repositories/saved/{repository_id}/jobs/{job_id}` — read owner-scoped indexing/embedding progress
- `POST /api/v1/repositories/saved/{repository_id}/embeddings` — queue configured embedding generation for the current indexed snapshot
- `POST /api/v1/repositories/saved/{repository_id}/search` — search the current indexed snapshot with keyword, semantic or hybrid retrieval
- `POST /api/v1/repositories/saved/{repository_id}/chat` — ask a grounded RAG question and persist the reply with citations
- `GET /api/v1/repositories/saved/{repository_id}/conversations` and `GET /api/v1/repositories/saved/{repository_id}/conversations/{conversation_id}` — list/read saved chats
- `POST /api/v1/repositories/inspect` — public metadata preview
- `GET /api/v1/repositories/{owner}/{repository}/contents` — public directory listing with optional `path` and `ref`

## Tests

Backend (with the backend virtual environment active):

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

GitHub Actions starts a local PostgreSQL service without Docker, applies the Alembic migrations, runs the backend tests, checks the live database schema, and builds the frontend.

## Security boundaries

- Passwords are hashed with Argon2; plaintext passwords are not stored.
- Access tokens are signed JWTs with issuer, audience and expiry claims. The browser keeps the token in `sessionStorage` for the current tab/session.
- Every saved-repository list, update, branch lookup, and delete is scoped by the authenticated user ID. Unknown IDs and records owned by other users return the same 404 response.
- Repository URLs are restricted to HTTPS on the exact GitHub host. The server connects only to the fixed `api.github.com` origin and uses curated response fields.
- Only public GitHub repositories are supported. No GitHub token, OAuth, or private-repository access is used.

**Before public internet deployment:** add login/registration rate limiting, email verification, password reset/recovery, security monitoring, HTTPS and managed secrets. This phase provides account and ownership foundations but is not a substitute for a full production security review. Do not commit `.env`, credentials, private code, or user data.

## Roadmap

- [x] Phase 1A/1B: foundation, responsive UI, URL validation and tests
- [x] Phase 2A/2B: PostgreSQL schema, migrations, schema checker and live DB CI
- [x] Phase 3A: public GitHub metadata and directory browsing
- [x] Phase 3B implementation: authentication, persistent owned repositories and branch selection (review and verify this phase before continuing)
- [x] Phase 4A implementation: bounded source fetching, safe file filtering, chunking, persistent indexing jobs and snapshot management (verify before continuing)
- [x] Phase 4B: configurable embeddings, versioned vector storage and embedding jobs
- [x] Phase 5 implementation: pgvector semantic retrieval, PostgreSQL full-text search, hybrid ranking and citations (verify before continuing)
- [x] Phase 6 implementation: grounded RAG chat, persistent conversations, and validated source citations (verify before continuing)
- [x] Phase 7 implementation: OpenRouter chat/embedding integration, bounded retries, copy-answer UX, and offline retrieval/citation evaluation (verify before continuing)
- [x] Phase 8 implementation: production configuration checks, trusted hosts, security headers, deployment runbook, and release package (review and verify before deploying)

See [Phase 3B notes](docs/PHASE_3B.md), [Phase 4A notes](docs/PHASE_4A.md), [Phase 4B notes](docs/PHASE_4B.md), [Phase 5 notes](docs/PHASE_5.md), [Phase 6 notes](docs/PHASE_6.md), [Phase 7 notes](docs/PHASE_7.md), and [Phase 8 notes](docs/PHASE_8.md) for implementation details and validation boundaries.
