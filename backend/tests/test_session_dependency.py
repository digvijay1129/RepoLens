"""Request session cleanup tests using a fake session."""

import pytest

from app.db import session as db_session


class FakeSession:
    def __init__(self) -> None:
        self.rollback_called = False
        self.close_called = False

    def rollback(self) -> None:
        self.rollback_called = True

    def close(self) -> None:
        self.close_called = True


def test_session_dependency_closes_session_after_success(monkeypatch) -> None:
    fake = FakeSession()
    monkeypatch.setattr(db_session, "get_database_url", lambda: "normalized-url")
    monkeypatch.setattr(
        db_session,
        "_build_session_factory",
        lambda _url: lambda: fake,
    )

    dependency = db_session.get_db_session()
    assert next(dependency) is fake

    with pytest.raises(StopIteration):
        next(dependency)

    assert fake.close_called
    assert not fake.rollback_called


def test_session_dependency_rolls_back_and_closes_after_error(monkeypatch) -> None:
    fake = FakeSession()
    monkeypatch.setattr(db_session, "get_database_url", lambda: "normalized-url")
    monkeypatch.setattr(
        db_session,
        "_build_session_factory",
        lambda _url: lambda: fake,
    )

    dependency = db_session.get_db_session()
    assert next(dependency) is fake

    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    assert fake.rollback_called
    assert fake.close_called
