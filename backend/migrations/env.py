"""Alembic environment wired to RepoLens settings and model metadata."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401 -- register all models with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
if not settings.database_url or not settings.database_url.strip():
    raise RuntimeError(
        "DATABASE_URL is required for Alembic. Copy backend/.env.example to backend/.env "
        "and configure PostgreSQL before running migrations."
    )

database_url = make_url(settings.database_url.strip())
if database_url.drivername == "postgresql":
    database_url = database_url.set(drivername="postgresql+psycopg")
if database_url.drivername != "postgresql+psycopg":
    raise RuntimeError("RepoLens migrations require PostgreSQL with the psycopg 3 driver.")

config.set_main_option(
    "sqlalchemy.url",
    database_url.render_as_string(hide_password=False).replace("%", "%%"),
)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate migration SQL without opening a database connection."""
    context.configure(
        url=database_url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a short-lived SQLAlchemy connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
