"""Schema and ownership tests using in-memory SQLite."""

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import IndexingJob, Repository, User


@pytest.fixture()
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def test_initial_schema_has_expected_tables_and_indexes() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) == {"users", "repositories", "indexing_jobs"}
    assert "uq_repositories_user_full_name" in {
        constraint["name"] for constraint in inspector.get_unique_constraints("repositories")
    }
    assert {index["name"] for index in inspector.get_indexes("indexing_jobs")} == {
        "ix_indexing_jobs_repository_created",
        "ix_indexing_jobs_user_status_created",
    }
    engine.dispose()


def test_user_repository_and_indexing_job_round_trip(session: Session) -> None:
    user = User(email="developer@example.com", display_name="Developer")
    session.add(user)
    session.flush()

    repository = Repository(
        user_id=user.id,
        github_owner="digvijay1129",
        github_name="RepoLens",
        full_name="digvijay1129/repolens",
        canonical_url="https://github.com/digvijay1129/RepoLens",
    )
    session.add(repository)
    session.flush()

    job = IndexingJob(user_id=user.id, repository_id=repository.id)
    session.add(job)
    session.commit()

    assert user.id is not None
    assert repository.indexing_status == "pending"
    assert job.status == "queued"
    assert job.attempt_count == 0
    assert job.repository.full_name == "digvijay1129/repolens"
    assert job.owner.email == "developer@example.com"


def test_database_rejects_index_job_for_repository_owned_by_another_user(session: Session) -> None:
    owner = User(email="owner@example.com")
    other_user = User(email="other@example.com")
    session.add_all([owner, other_user])
    session.flush()

    repository = Repository(
        user_id=owner.id,
        github_owner="org",
        github_name="project",
        full_name="org/project",
        canonical_url="https://github.com/org/project",
    )
    session.add(repository)
    session.flush()

    malicious_job = IndexingJob(repository_id=repository.id, user_id=other_user.id)
    session.add(malicious_job)

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_duplicate_repository_for_same_user_is_rejected(session: Session) -> None:
    user = User(email="unique@example.com")
    session.add(user)
    session.flush()
    values = {
        "user_id": user.id,
        "github_owner": "org",
        "github_name": "project",
        "full_name": "org/project",
        "canonical_url": "https://github.com/org/project",
    }
    session.add(Repository(**values))
    session.commit()

    session.add(Repository(**values))
    with pytest.raises(IntegrityError):
        session.commit()
