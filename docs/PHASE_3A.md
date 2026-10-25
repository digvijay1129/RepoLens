# Phase 3A — Public GitHub repository inspection and browsing

## Scope

Phase 3A adds a real read-only connection to GitHub's unauthenticated REST API for public repositories. It deliberately does not fetch or persist source file content.

## Implemented

- GitHub URL validation on both the React client and Python API.
- Fixed upstream origin: https://api.github.com; no caller-controlled host or redirect following.
- Curated repository metadata (default branch, language, stars, forks, issues, description, license, update time).
- Directory listing for a repository owner/name, optional repository-relative path, and optional ref.
- Validation for URL schemes, lookalike hosts, embedded credentials, query/fragment values, malformed owner/name, encoded path separators, traversal paths, backslashes, control characters, and oversized path/ref values.
- Safe handling for not-found responses, API rate limits, upstream errors, and timeouts.
- React repository list, metadata cards, directory breadcrumbs, folder navigation, loading/error/empty states, refresh action, and links to the corresponding GitHub source pages.
- Backend tests for URL/path validation, curated payloads, upstream errors/rate limiting, route behavior, and UI/API tests for successful and failed connection flows.
- Documentation and CI coverage.

## API

### POST /api/v1/repositories/inspect

Request:

```json
{
  "repository_url": "https://github.com/owner/repository"
}
```

Returns a curated metadata object. Invalid input returns HTTP 422; unknown/private repositories return 404; GitHub rate limits return 429; upstream availability failures return a safe 502.

### GET /api/v1/repositories/{owner}/{repository}/contents

Optional query parameters:
- `path`: repository-relative directory path.
- `ref`: branch, tag, or commit ref.

Returns directory items only. A path resolving to a file returns HTTP 400. GitHub's directory contents endpoint can be truncated at 1,000 entries; RepoLens marks this condition and informs the user.

## Persistence and identity boundary

Connections are stored only in React session memory in this phase. We do not write users/repositories to PostgreSQL yet, because user authentication and ownership checks must be implemented before adding persisted repository routes. Private repository access is not supported.

## Local verification

Run the backend and frontend using the repository root README. Then:

1. Paste a public repository URL in the connection modal.
2. Confirm metadata loads and the explorer page opens.
3. Open a folder and confirm a new directory listing is requested.
4. Click a file and confirm it opens the file's GitHub page in a new tab.
5. Try a non-existent public repository and confirm a safe not-found message.
6. Try a lookalike host such as `https://github.com.evil.test/owner/repo` and confirm the client rejects it before making an API request.
7. Test a narrow/mobile viewport and verify the file list is still usable.
8. Run `pytest`, `npm test`, and `npm run build`.

## Not included

- GitHub OAuth or private repositories
- Branch discovery/selection UI
- Database persistence of repositories
- Downloading source content, syntax parsing, indexing, embeddings, pgvector, RAG, or LLM chat
- Execution of any fetched repository code

Phase 3B will build on this slice after the live public-repository browsing API and UI are verified.
