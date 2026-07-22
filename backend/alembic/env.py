"""Alembic environment.

Uses the app's Settings + sync engine helpers so migrations run against the
same DATABASE_URL / DATABASE_TYPE as the running application. Works for both
SQLite and PostgreSQL.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure model metadata is fully populated before autogenerate / online runs.
from app.database import Base, to_sync_url  # noqa: E402
import app.models  # noqa: F401, E402  — register all tables on Base.metadata

# Alembic Config object (alembic.ini values).
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_database() -> tuple[str, str]:
    """Return (database_type, sync_url) from env / Settings.

    SECRET_KEY is not required for migrations; fall back to a placeholder so
    Settings can still validate when only DATABASE_* is set.
    """
    database_type = os.environ.get("DATABASE_TYPE", "sqlite").lower().strip()
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        # Lazy import Settings only when needed; inject a dummy SECRET_KEY if
        # missing so `alembic upgrade` works out of the box for local SQLite.
        os.environ.setdefault("SECRET_KEY", "alembic-migration-placeholder")
        from app.config import get_settings

        settings = get_settings()
        database_type = settings.DATABASE_TYPE
        database_url = settings.DATABASE_URL

    sync_url = to_sync_url(database_url, database_type)
    return database_type, sync_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout)."""
    _database_type, url = _resolve_database()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite-friendly ALTER TABLE support
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to the live database)."""
    _database_type, url = _resolve_database()

    # Ensure SQLite parent directory exists for file-backed DBs.
    from app.database import _ensure_sqlite_parent_dir

    if _database_type == "sqlite":
        _ensure_sqlite_parent_dir(url)

    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
