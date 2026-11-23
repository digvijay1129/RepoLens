<div align="center">

# RepoLens

### Understand a GitHub codebase with AI-powered search, grounded answers, and read-only agent workflows.

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React-61DAFB?logo=react&logoColor=20232A)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/Retrieval-pgvector-336791)](https://github.com/pgvector/pgvector)

**RepoLens** is a codebase intelligence workspace for public GitHub repositories. It indexes a commit-pinned source snapshot, finds relevant code with keyword and vector retrieval, and answers questions with source citations. Its agent workspace adds structured planning, specialist coordination, persistent repository memory, and owner-controlled execution of read-only tools.

</div>

---

## Overview

Understanding an unfamiliar codebase often means jumping between files, tracing dependencies, and manually searching for implementation details. RepoLens brings those activities into one workspace.

Connect a public GitHub repository, select a branch, index its source, and then search or ask questions about the selected snapshot. Results retain file paths and line ranges so answers can be checked against the original code.

## Key capabilities

| Capability | What it does |
|---|---|
| **Repository workspace** | Connect public GitHub repositories, browse files, select branches, and save repositories to an authenticated workspace. |
| **Commit-pinned indexing** | Index a specific commit using bounded, allowlisted source-file ingestion. |
| **Code search** | Search with PostgreSQL full-text search, pgvector semantic similarity, or hybrid retrieval. |
| **Grounded AI chat** | Ask questions about indexed code and receive answers with source citations. |
| **Agent planning** | Turn a repository goal into a structured, dependency-aware task plan. |
| **Specialist coordination** | Delegate plan steps across research, code-analysis, architecture, debugging, and documentation roles. |
| **Human approval controls** | Review exact proposed tool names and arguments, then approve or deny execution. |
| **Repository memory** | Keep owner-scoped notes, decisions, conventions, and observations for a repository. |
| **Retrieval evaluation** | Evaluate retrieval and citation quality with Recall@k, MRR, nDCG, validity, support precision, and coverage metrics. |

### Agent workspace

The agent dashboard provides task creation and progress, specialist assignments, approval decisions, repository memory, and tool execution history.

Agent tools are read-only. RepoLens does not execute repository code, run shell commands, write to a checked-out repository, or make remote GitHub mutations. Approval controls govern the execution of registered read-only tools; they do not enable arbitrary code execution.

## How it works

~~~mermaid
flowchart TD
    A[Connect public GitHub repository] --> B[Choose branch and resolve commit]
    B --> C[Fetch allowlisted source files]
    C --> D[Chunk source and store metadata]
    D --> E[(PostgreSQL)]
    D --> F[Optional embedding generation]
    F --> G[(pgvector)]
    E --> H[Keyword search]
    G --> I[Semantic search]
    H --> J[Hybrid ranking with RRF]
    I --> J
    J --> K[Retrieved source with file and line references]
    K --> L[AI chat with bounded source context]
    L --> M[Answer with citations]

    A --> N[Agent task planner]
    N --> O[Structured plan and specialist assignments]
    O --> P[Read-only repository tools]
    P --> Q[Approval and execution audit]
~~~

### Retrieval modes

| Mode | Description | Requirement |
|---|---|---|
| **Keyword** | PostgreSQL full-text search over indexed source chunks. | A completed source index. |
| **Semantic** | Vector similarity search over embedded chunks. | Embeddings generated for the selected snapshot. |
| **Hybrid** | Combines keyword and semantic rankings using Reciprocal Rank Fusion (RRF). | A source index and compatible embeddings. |

Keyword search remains available when embedding generation is disabled.

## Technology stack

| Layer | Technologies |
|---|---|
| Frontend | React 18, Vite, React Router, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic Settings |
| Database access | SQLAlchemy 2, Alembic |
| Database | PostgreSQL 16+, pgvector, PostgreSQL full-text search |
| Retrieval | Source chunking, cosine similarity, Reciprocal Rank Fusion |
| AI integration | OpenAI-compatible chat and embedding APIs; OpenRouter configuration |
| Authentication | Argon2 password hashing, signed JWT access tokens |
| Testing | pytest, Vitest, React Testing Library |
| CI | GitHub Actions |

## Project structure

~~~text
RepoLens/
├── .github/
│   └── workflows/             # CI workflows
├── backend/
│   ├── app/
│   │   ├── agents/             # Planning, orchestration, memory and read-only tools
│   │   ├── api/
│   │   │   ├── routes/         # REST endpoints
│   │   │   └── schemas/        # API request and response models
│   │   ├── core/               # Application settings and security
│   │   ├── db/                 # Database setup and schema checks
│   │   ├── evaluation/         # Retrieval and citation evaluation
│   │   ├── models/             # Persistent data models
│   │   ├── services/           # GitHub, indexing, retrieval, embeddings and LLM services
│   │   └── main.py             # FastAPI entry point
│   ├── evaluation/examples/    # Example evaluation input
│   ├── migrations/             # Alembic migrations
│   ├── tests/                  # Backend tests
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/         # Shared UI components
│   │   ├── lib/                # API and utility modules
│   │   ├── pages/              # Workspace pages
│   │   └── styles.css
│   ├── .env.example
│   └── package.json
├── scripts/                    # Project utility scripts
├── SECURITY.md
└── README.md
~~~

## Getting started

### Prerequisites

- Python 3.12 or newer
- Node.js 22.12 or newer and npm
- PostgreSQL 16 or newer
- pgvector installed for your PostgreSQL server
- Git

RepoLens uses a local Python and PostgreSQL development setup. Docker is not required.

### 1. Clone the repository

~~~powershell
git clone https://github.com/digvijay1129/RepoLens.git
cd RepoLens
~~~

### 2. Create the PostgreSQL database

Connect to PostgreSQL as an administrator and create a dedicated application user and database. Use a strong local password.

~~~sql
CREATE USER repolens_user WITH PASSWORD 'replace_with_a_strong_local_password';
CREATE DATABASE repolens OWNER repolens_user;
~~~

Connect to the new database and enable pgvector:

~~~sql
CREATE EXTENSION IF NOT EXISTS vector;
~~~

The pgvector server extension must be installed before it can be enabled in the database.

### 3. Configure and run the backend

From the repository root, in PowerShell:

~~~powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
~~~

Edit **backend/.env** and set at least:

- **DATABASE_URL** — the connection string for your local RepoLens database.
- **JWT_SECRET_KEY** — a private signing secret. Generate one with:

~~~powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
~~~

Apply migrations and check the database schema:

~~~powershell
alembic upgrade head
alembic current
python -m app.db.schema_check
~~~

Start the API:

~~~powershell
uvicorn app.main:app --reload
~~~

Backend URLs:

- API base: http://127.0.0.1:8000
- OpenAPI interface: http://127.0.0.1:8000/docs
- Liveness: http://127.0.0.1:8000/api/v1/health/live
- Readiness: http://127.0.0.1:8000/api/v1/health/ready

### 4. Configure and run the frontend

Open a second terminal from the repository root:

~~~powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
~~~

The frontend API base URL is configured by **VITE_API_BASE_URL** in frontend/.env. The example value points to http://127.0.0.1:8000. Open the local URL printed by Vite, normally http://localhost:5173.

### 5. Enable optional AI services

Chat and embedding generation are optional. The backend example configuration includes OpenRouter-compatible settings. To enable these features, add your private provider key and select models supported by your provider in **backend/.env**.

~~~dotenv
OPENROUTER_API_KEY=your_private_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_CHAT_MODEL=your_supported_chat_model
OPENROUTER_EMBEDDING_MODEL=your_supported_embedding_model

LLM_ENABLED=true
EMBEDDINGS_ENABLED=true
EMBEDDINGS_DIMENSIONS=1536
~~~

Keep provider credentials in backend environment variables. Never put API keys in frontend variables or commit environment files.

- **Keyword search** works without an embedding provider.
- **Semantic and hybrid search** require embeddings for the selected repository snapshot.
- **AI chat** requires an enabled chat provider.
- Embedding dimensions must match the configured vector dimensions.

Provider calls may incur costs. Retrieved source excerpts and bounded conversation context are sent to the configured model provider. Only index code you are authorized to share, and review the provider's privacy and retention terms.

## Using RepoLens

1. **Sign in** or create an account in the workspace.
2. **Connect a repository** by entering the URL of a public GitHub repository.
3. **Select a branch** and index the source snapshot.
4. **Search the code** with keyword search, or enable embeddings for semantic and hybrid retrieval.
5. **Ask a question** about the indexed code and inspect the returned file and line citations.
6. **Create an agent task** with a repository goal, review the generated plan, and run it.
7. **Control tool execution** through the approval center and inspect task history, repository memory, and tool results.

## API overview

The backend exposes versioned REST endpoints under **/api/v1**. The running API's OpenAPI interface at **/docs** shows the available request and response schemas.

| Area | Main operations |
|---|---|
| Health | Liveness and readiness checks |
| Authentication | Register, log in, and retrieve the current account |
| Repositories | Inspect, save, browse, select branches, and manage repository snapshots |
| Indexing | Start source indexing and inspect job status |
| Embeddings | Generate embeddings for an indexed snapshot |
| Search and chat | Search source chunks and ask repository-grounded questions |
| Agent tasks | Create, inspect, run, resume, and cancel agent tasks |
| Agent controls | Review approvals, inspect tool executions, and manage repository memory |

Protected workspace resources are scoped to the authenticated user.

## Testing

Run backend tests and schema checks from the backend directory:

~~~powershell
pytest
python -m app.db.schema_check
~~~

Run frontend tests and create a production build from the frontend directory:

~~~powershell
npm test
npm run build
~~~

The backend also includes an offline retrieval evaluation utility. Its sample input is illustrative; meaningful evaluation requires representative queries and human-reviewed relevance and citation-support labels.

## Security and project scope

- Only public GitHub repositories are supported; private-repository OAuth access is not implemented.
- Repository files are ingested as source text and are never executed.
- Agent repository tools are read-only; shell execution, filesystem writes, and remote GitHub mutations are not enabled.
- Passwords are hashed with Argon2, and API access uses signed JWT tokens.
- Repository data and workspace operations are scoped to the authenticated user.
- Retrieved source and conversation content are untrusted inputs to AI prompts.
- Keep database passwords, JWT secrets, and provider API keys out of Git.

See [SECURITY.md](SECURITY.md) for the project's security policy.

---

<div align="center">

**RepoLens — Explore, search, and understand codebases with traceable AI assistance.**

</div>
