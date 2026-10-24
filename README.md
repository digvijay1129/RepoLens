# RepoLens

GitHub Codebase Intelligence Assistant powered by retrieval-augmented generation (RAG).

> Phase 1 foundation. Repository indexing, PostgreSQL persistence, embeddings, and LLM chat are introduced in later verified phases.

## Planned stack

- Frontend: React, Vite, TypeScript
- Backend: Python 3.12+, FastAPI, Pydantic
- Data: PostgreSQL + pgvector (later phase)
- Integration: GitHub REST API, embedding provider, LLM API (later phases)
- No Docker; no model training.

## Repository status

Phase 1A establishes the project baseline. Follow each phase's verification steps before moving on. Do not commit `.env`, tokens, credentials, or private repository source.

## Local development

See `docs/PHASE_1.md` for the current setup and verification instructions.
