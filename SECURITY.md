# Security Policy

## Supported configuration

RepoLens is an educational/developer project. Use current dependencies and follow the production setup documented in `docs/PHASE_8.md`. Do not index source code that you are not authorized to share with the configured LLM provider.

## Reporting a vulnerability

Please do not publish API keys, database credentials, private code, or exploitable details in a public issue. Use GitHub's private vulnerability reporting for this repository if it is enabled. If private reporting is not available, contact the repository owner privately before sharing technical details publicly.

## Secret handling

- Never commit `.env` or real API credentials.
- Rotate credentials immediately if they are exposed.
- Keep OpenRouter keys and database/JWT secrets backend-only.
- Review hosting logs and crash reports for accidental secret disclosure before sharing them.
