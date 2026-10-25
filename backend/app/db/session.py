"""SQLAlchemy engine and request-scoped session dependencies."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


class DatabaseConfigurationError(RuntimeError):
    """Raised when database configuration is missing or unsupported."""


@lru_cache(maxsize=4)
def _build_engine(normalized_url: str) -> Engine:
    """Create a pooled engine per URL; database connections open lazily."""
    return create_engine(
        normalized_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
    )


@lru_cache(maxsize=4)
def _build_session_factory(normalized_url: str) -> sessionmaker[Session]:
    """Reuse a session factory for each configured database URL."""
    return sessionmaker(
        bind=_build_engine(normalized_url),
        autoflush=False,
        expire_on_commit=False,
    )


def get_database_url() -> str:
    """Return a normalized driver URL or raise a safe configuration error."""
    raw_url = get_settings().database_url
    if not raw_url or not raw_url.strip():
        raise DatabaseConfigurationError(
            "DATABASE_URL is not configured. Copy backend/.env.example to backend/.env "
            "and set the PostgreSQL connection URL."
        )

    try:
        url = make_url(raw_url.strip())
    except ArgumentError as exc:
        raise DatabaseConfigurationError("DATABASE_URL is not a valid SQLAlchemy URL.") from exc

    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername != "postgresql+psycopg":
        raise DatabaseConfigurationError(
            "RepoLens requires PostgreSQL using the psycopg 3 driver."
        )

    if not url.database or not url.username:
        raise DatabaseConfigurationError(
            "DATABASE_URL must include a PostgreSQL database name and username."
        )

    return url.render_as_string(hide_password=False)


def get_engine() -> Engine:
    """Return the configured PostgreSQL engine."""
    return _build_engine(get_database_url())


def get_db_session() -> Generator[Session, None, None]:
    """Yield a request-scoped session and always close it afterwards."""
    session = _build_session_factory(get_database_url())()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection() -> None:
    """Open a short-lived connection and execute a minimal readiness query."""
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
