"""Ensure the Alembic revision graph is a single linear history."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.base import Base
import app.models  # noqa: F401 -- register models for metadata assertions


def test_alembic_has_a_linear_twelve_revision_history() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    revisions = {revision.revision: revision for revision in script.walk_revisions()}

    assert set(revisions) == {"20261025_0001", "20261025_0002", "20261025_0003", "20261025_0004", "20261025_0005", "20261025_0006", "20261025_0007", "20261122_0008", "20261122_0009", "20261122_0010", "20261122_0011", "20261122_0012"}
    assert revisions["20261025_0001"].down_revision is None
    assert revisions["20261025_0002"].down_revision == "20261025_0001"
    assert revisions["20261025_0003"].down_revision == "20261025_0002"
    assert revisions["20261025_0004"].down_revision == "20261025_0003"
    assert revisions["20261025_0005"].down_revision == "20261025_0004"
    assert revisions["20261025_0006"].down_revision == "20261025_0005"
    assert revisions["20261025_0007"].down_revision == "20261025_0006"
    assert revisions["20261122_0008"].down_revision == "20261025_0007"
    assert revisions["20261122_0009"].down_revision == "20261122_0008"
    assert revisions["20261122_0010"].down_revision == "20261122_0009"
    assert revisions["20261122_0011"].down_revision == "20261122_0010"
    assert revisions["20261122_0012"].down_revision == "20261122_0011"
    assert script.get_current_head() == "20261122_0012"


def test_model_metadata_has_expected_tables() -> None:
    assert set(Base.metadata.tables) == {"users", "repositories", "indexing_jobs", "repository_chunks", "repository_chunk_embeddings", "chat_conversations", "chat_messages", "agent_tasks", "agent_plans", "agent_steps", "agent_tool_executions", "agent_memories", "agent_delegations"}


def test_models_include_phase_3b_persistence_fields() -> None:
    assert {"password_hash", "is_active"} <= set(Base.metadata.tables["users"].columns.keys())
    assert {
        "github_repository_id", "description", "language", "selected_branch",
        "github_updated_at", "stargazers_count",
    } <= set(Base.metadata.tables["repositories"].columns.keys())
    assert {"total_files", "processed_files", "skipped_files", "chunk_count", "commit_sha"} <= set(
        Base.metadata.tables["indexing_jobs"].columns.keys()
    )
    assert {"file_path", "chunk_text", "content_hash", "symbol_names", "commit_sha", "start_line", "end_line"} <= set(
        Base.metadata.tables["repository_chunks"].columns.keys()
    )
    assert {"embedding_status", "embedding_provider", "embedding_model", "embedding_dimensions", "last_embedded_at"} <= set(
        Base.metadata.tables["repositories"].columns.keys()
    )
    assert {"job_type", "embedding_provider", "embedding_model", "embedding_dimensions"} <= set(
        Base.metadata.tables["indexing_jobs"].columns.keys()
    )
    assert {"provider", "model", "dimensions", "content_hash", "vector"} <= set(
        Base.metadata.tables["repository_chunk_embeddings"].columns.keys()
    )



def test_agent_models_include_owner_scoped_persistence_fields() -> None:
    assert {
        "indexed_commit_sha", "goal", "status", "max_steps", "max_tool_calls",
        "max_retries_per_step", "total_tool_calls", "total_retries", "final_result",
        "execution_started_at", "execution_finished_at", "latest_error",
    } <= set(
        Base.metadata.tables["agent_tasks"].columns.keys()
    )
    assert {"version", "summary", "completion_criteria", "assumptions", "planner_provider", "planner_model"} <= set(
        Base.metadata.tables["agent_plans"].columns.keys()
    )
    assert {"position", "step_key", "title", "description", "rationale", "expected_output", "suggested_tool", "depends_on", "status"} <= set(
        Base.metadata.tables["agent_steps"].columns.keys()
    )



def test_agent_tool_execution_model_is_auditable_and_owner_scoped() -> None:
    assert {
        "provider_call_id", "tool_name", "status", "tool_input", "tool_output",
        "error_message", "duration_ms", "created_at", "finished_at",
    } <= set(Base.metadata.tables["agent_tool_executions"].columns.keys())



def test_agent_memory_model_has_owner_scoped_provenance_and_limits() -> None:
    columns = set(Base.metadata.tables["agent_memories"].columns.keys())
    assert {
        "user_id", "repository_id", "task_id", "source_execution_id",
        "memory_type", "origin", "title", "content", "tags", "source_refs",
        "source_commit_sha", "content_hash", "confidence", "importance",
        "is_active", "access_count", "last_accessed_at", "expires_at",
    } <= columns



def test_agent_delegation_model_has_specialist_and_owner_scoped_fields() -> None:
    columns = set(Base.metadata.tables["agent_delegations"].columns.keys())
    assert {
        "task_id", "step_id", "user_id", "repository_id", "source_execution_id",
        "specialist_key", "specialist_name", "mission", "status", "attempt_number",
        "assignment_context", "result_summary", "error_message", "started_at", "finished_at",
    } <= columns
