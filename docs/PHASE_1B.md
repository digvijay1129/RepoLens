# Phase 1B — Foundation hardening and frontend tests

## Goal

Improve the Phase 1A foundation before database or repository integration. This phase adds validated GitHub repository URL parsing, accessible modal behavior, and repeatable frontend tests. It does **not** fetch repository content or call any AI provider.

## Changes in this phase

- Extract GitHub repository URL parsing into a small pure JavaScript helper that can be unit tested.
- Accept HTTPS URLs on the exact `github.com` host with an owner and one repository name.
- Normalize optional trailing slashes and `.git` suffixes.
- Reject insecure URLs, lookalike hosts, credentials, query strings/fragments, unexpected nested routes, and invalid encoded path segments.
- Improve connect-modal keyboard behavior: Escape closes it, focus starts in the URL field, focus stays within the dialog when tabbing, and focus returns to the opener after close.
- Mark validation errors with `role="alert"` and `aria-invalid`.
- Add Vitest and React Testing Library tests for helper validation and core UI behavior.
- Extend GitHub Actions to run frontend unit tests as well as a production build on the Phase 1B branch.
- Expand ignored test artifacts and update setup docs.

## Not included

- Real GitHub API requests, GitHub OAuth, or private-repository support
- Database models or PostgreSQL/pgvector connection
- Embeddings, indexing jobs, RAG retrieval, or LLM chat
- User accounts or server-side authorization
- Deployment to production

## Run locally

Install Node.js 22.12+ and npm. From the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm test
npm run build
npm run dev
```

In macOS/Linux, use `cp .env.example .env` for environment-file setup.

Run backend checks separately:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
```

## What is tested

1. Valid GitHub repository URL normalization.
2. Whitespace, trailing slash, and optional `.git` handling.
3. Rejection of non-HTTPS URLs, lookalike hosts, query strings, fragments, credentials, nested file/issue URLs, and encoded path separators.
4. Main dashboard render and online/offline API status.
5. Accessible validation error feedback when invalid input is submitted.
6. Valid URL preview does not claim to fetch or persist repository data.
7. Escape closes the modal.
8. Suggested questions remain clearly labeled preview behavior.

## Acceptance checklist

- [ ] Frontend tests pass locally with `npm test`.
- [ ] Frontend production build passes with `npm run build`.
- [ ] Backend tests pass with `pytest`.
- [ ] The dashboard is usable at desktop and mobile viewport widths.
- [ ] Invalid repository URLs show an accessible error and do not close the modal.
- [ ] Escape closes the modal, and keyboard focus is returned to the opener.
- [ ] The GitHub Actions run for this branch completes successfully.
- [ ] The pull request diff contains no `.env`, credentials, tokens, private repository contents, or unnecessary uploads.

## Phase boundary

Phase 1B is only the hardened shell and test suite. Start Phase 2 only after verifying these acceptance checks and approving the next step. Phase 2 will introduce PostgreSQL, SQLAlchemy, Alembic, and schema tests.
