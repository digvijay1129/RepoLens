# Phase 3A — Public GitHub repository inspection and browsing

Phase 3A introduced the real, read-only integration for public GitHub repositories:
- `POST /api/v1/repositories/inspect` returns curated public metadata.
- `GET /api/v1/repositories/{owner}/{repository}/contents` lists the entries in a repository directory.
- The backend uses a fixed GitHub API host, validates repository URLs and repository-relative paths, and handles upstream errors safely.
- The React code explorer displays repository information, breadcrumbs, folder navigation, loading/error states, and links to files on GitHub.

Phase 3B extends this public viewer with account authentication, owner-scoped PostgreSQL persistence, and branch selection. See [PHASE_3B.md](PHASE_3B.md).

Phase 3A alone did not persist repositories, fetch file contents, or provide private-repository access.
