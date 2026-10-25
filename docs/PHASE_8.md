# Phase 8 — Deployment preparation, security review, and release packaging

## Scope

Phase 8 adds explicit production settings validation, trusted-host checks, safer API defaults, response security headers, deployment documentation, and release hygiene. It does **not** mean the application is automatically security-certified or deployed to a hosting provider.

## Local setup (Windows / VS Code, no Docker)

1. Install Python 3.12+, Node.js 22.12+, PostgreSQL 16+, and the pgvector server extension compatible with the local PostgreSQL installation.
2. Create a local database and application user. Keep credentials unique to the local development database.
3. Copy `backend/.env.example` to `backend/.env` and set `DATABASE_URL` and a unique `JWT_SECRET_KEY` generated with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. Apply `CREATE EXTENSION IF NOT EXISTS vector;` in the RepoLens database with a PostgreSQL administrator, then run `alembic upgrade head` from `backend/`.
5. Install `backend/requirements.txt`, run `python -m app.db.schema_check` and `pytest`.
6. Copy `frontend/.env.example` to `frontend/.env`, then run `npm install`, `npm test`, `npm run build`, and `npm run dev` from `frontend/`.
7. Configure OpenRouter only if you want chat; enable embeddings separately only if you want semantic/hybrid retrieval.

Never commit `.env` files. The release ZIP intentionally contains only the safe `.env.example` files, not developer secrets, local virtual environments or dependencies.

## Production environment

Deploy the backend and frontend to a platform of your choice; no provider has been selected or configured by this phase. Terminate HTTPS at the hosting platform or reverse proxy, and configure these backend environment variables in the host's secret/settings UI:

```dotenv
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@DB_HOST:5432/DB_NAME?sslmode=verify-full
JWT_SECRET_KEY=<unique-random-secret-at-least-32-bytes>
CORS_ORIGINS=https://your-frontend.example.com
TRUSTED_HOSTS=your-api.example.com

OPENROUTER_API_KEY=<private-key-if-chat-is-enabled>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_CHAT_MODEL=openai/gpt-5.6-luna
OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small
OPENROUTER_HTTP_REFERER=https://your-frontend.example.com
OPENROUTER_APP_TITLE=RepoLens
LLM_ENABLED=true
EMBEDDINGS_ENABLED=false
```

Replace all example hosts and credentials. Managed database providers may prescribe a different connection URL or TLS option; use their certificate-verification mode where available. The production startup check rejects weak/missing JWT secrets, non-TLS remote database URLs, wildcard/non-HTTPS CORS origins, unsafe host lists, and a non-HTTPS OpenRouter referer when OpenRouter is configured.

Keep model keys, database credentials and JWT secrets in the hosting provider's secret store. Never expose `OPENROUTER_API_KEY` as a `VITE_*` variable. Calls to OpenRouter may cost money and send bounded source excerpts and conversation context to the provider; review its current privacy, retention, pricing, and rate-limit terms.

## Runbook

From `backend/` as part of deployment/release:

```powershell
python -m pip install -r requirements.txt
alembic upgrade head
python -m app.db.schema_check
pytest
```

For a local Windows developer machine, use `uvicorn app.main:app --reload`. For a production host, run without `--reload` behind the platform's HTTPS ingress, bind to its required interface/port, and use a process manager appropriate for that host.

- `GET /api/v1/health/live` checks process liveness without a database connection.
- `GET /api/v1/health/ready` checks database connectivity.
- Interactive `/docs`, `/redoc`, and `/openapi.json` endpoints are disabled when `ENVIRONMENT=production`.
- Production requests are checked by the trusted-host middleware.
- API responses carry `Cache-Control: no-store`; default security headers are added.
- Remote PostgreSQL must use an explicit SSL mode of `require`, `verify-ca`, or `verify-full`.

Use a least-privilege database account; create the `vector` extension with an administrator before running application migrations if the app account lacks extension permissions. Back up PostgreSQL, test restore procedures, rotate secrets if exposed, and keep Python/npm dependencies updated.

## Security review summary

Implemented in Phase 8:
- Fail-fast production environment validation for JWT key length, remote PostgreSQL TLS, public HTTPS CORS origins, trusted host names, and the OpenRouter referer.
- Trusted Host middleware in production.
- Disabled interactive API documentation in production.
- `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy` response headers, and no-store caching for API responses.
- Regression tests for unsafe configuration, host rejection, documentation exposure and response headers.
- Explicit secret/temporary-file exclusions and documented deployment runbook.

Remaining pre-public-launch work:
- Add distributed rate limiting for login, registration, indexing, search and LLM calls. Do not rely on in-memory limits across multiple workers.
- Add password reset/recovery, email verification and account/session management.
- Decide and test a production GitHub access policy. Current repository ingestion is for public GitHub repositories only; don't promise private repository support.
- Add operational monitoring, structured redacted logs, alerting, database backup/restore drills and a defined retention policy.
- Configure actual hosting, TLS, DNS, trusted hosts, managed secrets, migrations and health probes in the selected provider.
- Consider LLM quotas/cost budgets and human-reviewed evaluation thresholds before enabling chat for broad public use.
- Conduct a separate external security review before handling sensitive source code or public production accounts.

## Release packaging

The release archive is generated from the reviewed source tree and excludes `.env`, local virtual environments, `node_modules`, build output and caches. It includes both `.env.example` templates, source code, migrations, tests, and documentation. No Docker or TypeScript is required.

The ZIP is a source package, not a prebuilt hosted service. On first run, install dependencies locally and configure PostgreSQL/pgvector and optional OpenRouter values as described above.
