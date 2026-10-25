# Phase 6 — Repository-grounded RAG chat and persistent history

## Scope

Phase 6 connects Phase 5 retrieval to an OpenAI-compatible chat-completion API. It answers questions using retrieved chunks from the currently indexed source snapshot and stores user/assistant messages plus citation metadata in PostgreSQL.

## Configuration

RAG chat is disabled by default. OpenRouter is the recommended configuration and uses one server-side key for chat plus optional embeddings:

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

# Optional: required only for semantic/hybrid retrieval and embedding generation
EMBEDDINGS_ENABLED=true
EMBEDDINGS_DIMENSIONS=1536
EMBEDDINGS_BATCH_SIZE=32
```

When `OPENROUTER_API_KEY` is non-empty, it overrides the legacy `LLM_API_KEY` and `EMBEDDINGS_API_KEY` credentials and the `OPENROUTER_*` base URL/model settings are used. Keep the key in `backend/.env`; never add it to frontend environment variables or Git. Set `OPENROUTER_HTTP_REFERER` to your deployed app origin in production. Chat-only mode uses keyword retrieval and does not require embeddings. Semantic/hybrid retrieval requires embeddings generated with the same model and dimensions.

The configured model IDs are listed in the OpenRouter catalog. Provider availability, price, rate limits and data handling can change; check OpenRouter before deploying. See [OpenRouter chat model](https://openrouter.ai/openai/gpt-5.6-luna), [embedding model](https://openrouter.ai/openai/text-embedding-3-small/providers), and [embeddings API](https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings).

LLM calls may incur cost. Retrieved source excerpts and selected chat history are sent to the configured provider, so review its retention/privacy terms and only index code you are authorized to share.

## Flow

1. Validate the authenticated owner of the saved repository and validate chat-provider configuration.
2. Look up or create a conversation belonging to that user and repository.
3. Retrieve top source chunks from the current indexed commit (hybrid when the active embedding configuration matches, keyword otherwise).
4. Provide the model a system message that treats repository text as untrusted evidence, bounded chat history, and a bounded JSON context with stable source labels such as `S1`.
5. Ask the model to support repository claims using labels `[S1]`, `[S2]`, etc. Unknown labels are rewritten to `[citation unavailable]`.
6. Persist the user question, assistant answer, and per-answer source metadata in PostgreSQL.
7. Return the conversation ID, answer, retrieved citation list and commit SHA to the UI.

When retrieval returns no relevant source chunks, the service gives a deterministic no-evidence response and does not call the LLM.

## API

- `POST /api/v1/repositories/saved/{repository_id}/chat` accepts `message` and an optional `conversation_id`. Omit the ID to start a new conversation.
- `GET /api/v1/repositories/saved/{repository_id}/conversations` lists recent conversation summaries.
- `GET /api/v1/repositories/saved/{repository_id}/conversations/{conversation_id}` returns the owner-scoped message history and stored sources.

Chat requests require an authenticated user, an owned saved repository, an indexed source snapshot, and valid LLM configuration. Conversation IDs from another user's workspace return not-found responses.

## UI

Code Explorer now includes **Ask RepoLens**, which provides:
- New chat and saved conversation history selector
- Multi-turn messages with loading and error states
- Citation cards with exact repository file paths and source line links
- An explicit note that retrieved source text is untrusted evidence
- A setup-friendly disabled/error state when the repository is not indexed or LLM is not configured

## Persistence and migration

Alembic revision `20261025_0007` adds `chat_conversations` and `chat_messages`. Messages retain their role, text, timestamps and the source-citation metadata used for the answer. Foreign keys tie each conversation to an owned repository and each message to the correct conversation/repository/user combination. The migration is additive; run `alembic upgrade head` against the existing database. Do not recreate or drop the database.

## Safety / limitations

- Retrieved source text and previous chat turns are untrusted context. System instructions explicitly tell the model not to follow instructions embedded in code/comments.
- Unknown citation labels are replaced with `[citation unavailable]`; the application still returns the exact list of retrieved source references separately.
- The backend limits chat input to 4,000 characters, result context count to 12, recent-history count to 16, and each historical message sent to the LLM to 2,500 characters.
- Only the configured provider sees the bounded retrieved excerpts and selected chat history. Review the provider's privacy and retention terms and only index code you're authorized to share.
- The prompt and citation layer improve grounding but do not guarantee a model will never make a mistake. Verify critical statements against the links.
- In-process requests are not streamed; this phase does not include distributed queues, usage quotas, feedback/evaluation dashboards or private GitHub OAuth.
- No Docker or TypeScript.

## Verification

CI includes tests for provider settings/response handling, prompt context, no-evidence behavior, conversation persistence/continuations, citation label validation, owner-scoped APIs, migration checks, frontend chat rendering, saved history calls, and the production build.
