# Phase 6 — Repository-grounded RAG chat and persistent history

## Scope

Phase 6 connects Phase 5 retrieval to an OpenAI-compatible chat-completion API. It answers questions using retrieved chunks from the currently indexed source snapshot and stores user/assistant messages plus citation metadata in PostgreSQL.

## Configuration

RAG chat is disabled by default and does not affect source indexing or keyword search. Set these values in `backend/.env` to enable it:

```dotenv
LLM_ENABLED=true
LLM_PROVIDER=openai_compatible
LLM_API_KEY=your_private_chat_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=60
LLM_MAX_COMPLETION_TOKENS=1200
RAG_CONTEXT_CHUNKS=8
RAG_HISTORY_MESSAGES=8
```

Model and endpoint examples must match your provider's available models. Keep all keys backend-only, never commit `backend/.env`, and restart FastAPI after changing settings. Remote provider URLs must use HTTPS; plain HTTP is accepted only for localhost during non-production development.

An LLM call may incur cost. For a repository with current embeddings matching the configured embedding model, chat uses hybrid retrieval; otherwise it uses keyword retrieval. This permits chat to work without embedding credentials, provided source indexing and a working LLM provider are configured.

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
