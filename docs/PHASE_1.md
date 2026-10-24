# Phase 1A — Foundation and interface shell

## Goal

Set up a clean, testable baseline before adding database, GitHub, embedding, or LLM behavior. This phase is a foundation, not a claim that the complete product is already functional.

## Included

- FastAPI entry point with a versioned API prefix
- Liveness and readiness health endpoints
- Environment settings and configurable CORS allow-list
- Automated health endpoint tests
- React + Vite frontend using JavaScript/JSX only
- Responsive dashboard with explicit empty states and future-feature messaging
- Setup docs and secret-safe ignore rules

## Not included yet

PostgreSQL/pgvector, schema/migrations, authentication, GitHub OAuth, repository ingestion, background workers, embeddings, RAG, LLM calls, persisted chat, or deployment. These will be added in later verified phases; no fake repository or AI results are shown.

## Backend setup

Windows PowerShell:

\`\`\`powershell
cd backend
py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
\`\`\`

macOS/Linux:

\`\`\`bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
\`\`\`

## Frontend setup

In another terminal:

\`\`\`bash
cd frontend
npm install
cp .env.example .env
npm run dev
\`\`\`

On Windows use \`Copy-Item .env.example .env\`.

## Verification checklist

1. Backend starts without import/configuration errors.
2. GET \`/api/v1/health/live\` returns \`{"status":"ok"}\`.
3. GET \`/api/v1/health/ready\` returns \`{"status":"ready"}\`.
4. \`/docs\` renders the API documentation and both health routes.
5. Run \`pytest\` from \`backend\`; all health tests should pass.
6. Start the frontend and open the URL shown by Vite.
7. Resize the browser and confirm the dashboard reflows for mobile.
8. Stop the backend and confirm the UI reports the API as offline.

Readiness means only that the API process is ready in Phase 1A. Phase 2 will include required database connectivity in the readiness check.

## Before pushing

Inspect \`git status --short\` and \`git diff --cached\`. Do not stage \`.env\`, tokens, passwords, private code, or credentials.
