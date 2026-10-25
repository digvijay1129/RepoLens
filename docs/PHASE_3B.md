# Phase 3B — Authenticated workspace, repository persistence, and branch selection

## Purpose

Phase 3B builds on the merged Phase 3A public GitHub viewer. It introduces account authentication, persists connected repository metadata in PostgreSQL, scopes workspace operations to the authenticated user, and makes branch selection persistent.

## Included

### Authentication
- `POST /api/v1/auth/register`: email, optional display name, password of at least 12 characters; creates an account and returns a short-lived access token.
- `POST /api/v1/auth/login`: verifies the Argon2 hash and returns a signed JWT. Invalid email and password use the same user-facing response.
- `GET /api/v1/auth/me`: returns the current active account profile.
- JWT validation checks the signing key, algorithm, issuer, audience, required claims, token type and expiry.
- Authentication endpoints stay unavailable until the local `JWT_SECRET_KEY` is configured with at least 32 bytes.
- The frontend uses a sign-in/register screen and keeps the bearer token in `sessionStorage`.

### Database migration
Migration `20261025_0003`:
- Adds nullable `users.password_hash` for compatible migration of legacy rows and a non-null `users.is_active` column.
- Adds public repository metadata fields: GitHub numeric ID (64-bit), description, language, counts, size, license, archived status and GitHub update time.
- Adds `repositories.selected_branch`, initialized from each repository's default branch when available.
- Adds non-negative check constraints for star, fork and issue counts.

Apply to an existing database with `alembic upgrade head`. Do not delete/recreate the database.

### Persisted repository workspace
- `POST /api/v1/repositories/saved` validates the public URL, fetches metadata from GitHub server-side, then stores a normalized record against the current user.
- `GET /api/v1/repositories/saved` lists only the current user's rows.
- `DELETE /api/v1/repositories/saved/{repository_id}` deletes only a row owned by the current user.
- Owner scoping is enforced inside every saved-record database query—not from a client-supplied owner header or user ID.
- Re-saving a repository owned by the same user refreshes its stored public metadata instead of adding a duplicate row.

### Branch selection
- `GET /api/v1/repositories/saved/{repository_id}/branches` checks row ownership before fetching public branches from GitHub.
- `PATCH /api/v1/repositories/saved/{repository_id}/branch` confirms the branch is in the available branch list before saving it.
- The frontend branch selector is populated from GitHub and persists changes; the code explorer uses the selected branch as its `ref` when requesting directories.
- Branch listing checks up to 500 names per request and flags when the returned list may be truncated.

## Local setup

1. Configure PostgreSQL in `backend/.env`.
2. Generate the JWT signing secret in PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

3. Paste the generated value into `JWT_SECRET_KEY=` in `backend/.env`. Do not commit that file.
4. From `backend/`, with the virtual environment active:

```powershell
alembic upgrade head
alembic current
python -m app.db.schema_check
pytest
```

5. In another terminal:

```powershell
cd frontend
npm install
npm test
npm run build
npm run dev
```

## Verification checklist

- [ ] Fresh registration returns a token; password values are never returned or stored in plaintext.
- [ ] Sign-in rejects incorrect credentials with the same generic message for unknown emails and wrong passwords.
- [ ] `/auth/me` rejects missing, malformed and expired tokens.
- [ ] Saved repositories persist after reload for the signed-in user.
- [ ] Account A cannot list, change a branch on, or delete Account B's repository record.
- [ ] Invalid branch names are rejected; valid selections persist and control the explorer's directory ref.
- [ ] Alembic migration applies on PostgreSQL through revision `20261025_0003`.
- [ ] Schema checker, backend tests, frontend tests and production build pass.

## Important security limits

- Only public GitHub repositories are supported; no OAuth/private repository token.
- JWT access tokens are short-lived and kept in browser `sessionStorage`; production deployment should use HTTPS.
- Email verification, password reset/recovery, signup/login rate limiting, logout revocation, and production secret management are not implemented in this phase. Add these before exposing registration to the public internet.
- Directory listing is public and read-only; this phase does not download or execute file contents, nor does it yet index repositories, create embeddings, use pgvector, or call an LLM.

Phase 3B should be reviewed and run against the developer's PostgreSQL instance before continuing with Phase 4A source indexing.
