# Phase 7 — OpenRouter, evaluation, reliability and UX

## OpenRouter configuration

RepoLens now supports these dedicated environment settings:

```dotenv
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_CHAT_MODEL=openai/gpt-5.6-luna
OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small
OPENROUTER_HTTP_REFERER=http://localhost:5173
OPENROUTER_APP_TITLE=RepoLens

LLM_ENABLED=true
LLM_TIMEOUT_SECONDS=60
LLM_MAX_COMPLETION_TOKENS=1200
LLM_MAX_RETRIES=2
RAG_CONTEXT_CHUNKS=8
RAG_HISTORY_MESSAGES=8

# Enable only when you want to build embeddings and use semantic/hybrid search.
EMBEDDINGS_ENABLED=true
EMBEDDINGS_DIMENSIONS=1536
EMBEDDINGS_BATCH_SIZE=32
```

The `OPENROUTER_API_KEY` value is read only by the backend and takes precedence over the legacy `LLM_API_KEY` and `EMBEDDINGS_API_KEY` settings. The dedicated OpenRouter model/base URL fields take precedence too. Chat and embeddings use the same OpenRouter API key; embeddings can remain disabled for keyword-only RAG. Both endpoints use HTTPS and send OpenRouter's optional `HTTP-Referer` and `X-Title` headers. Chat retries a small bounded number of times on retryable rate-limit/upstream responses; it avoids echoing provider response bodies or credentials in errors.

Set the HTTP referer to the real site origin when deploying. Never commit `backend/.env` or place the API key in frontend configuration. Provider calls can incur cost and the selected source excerpts/history are sent to OpenRouter, so check their current data policies, rate limits and price before using sensitive/private source code.

## Reliability and usability

- Chat requests now retry HTTP 429 and transient 502/503/504 responses with bounded backoff (`LLM_MAX_RETRIES` from 0 to 3).
- Answer UI provides a one-click copy action; citation links remain attached to answers.
- Existing owner checks, model/dimension guards, bounded chat history, no-evidence fallback and unknown-citation-label validation remain enabled.

## Offline evaluation harness

The new evaluation command measures quality on JSONL exports from actual RepoLens retrieval/chat runs. It does not call a model or need a database; retrieval IDs and human-reviewed supported citations are supplied by the evaluator.

Run the included illustrative sample from `backend/`:

```powershell
python -m app.evaluation.evaluate --input evaluation/examples/openrouter_rag_run.jsonl --k 5 --output evaluation/report.json
```

Each JSONL row must include:

- `query`: non-empty query text.
- `relevant_chunk_ids`: human-labelled relevant chunk IDs.
- `retrieved_chunk_ids`: ranked chunk IDs returned by RepoLens.
- `known_source_ids`: source labels supplied to the LLM (e.g. `S1`, `S2`).
- `cited_source_ids`: labels referenced in the answer.
- `supported_source_ids`: human-reviewed labels that actually support the answer.

The report includes Recall@k, mean reciprocal rank (MRR), nDCG@k, citation validity, citation support precision, citation coverage, unknown citations, and per-query results. The sample file is synthetic and demonstrates the input format only; do not use it as a real quality benchmark. Use representative, human-reviewed queries from your own repositories and compare metrics before/after retrieval or prompt changes.

## CI and version

Phase 7 CI still runs without Docker. It tests OpenRouter selection, headers, retry behavior, embedding compatibility, metrics, migrations, frontend behavior and the production build. The API version is now `0.8.0`; no schema migration is needed for this phase.
