"""SQLAlchemy engine / session factory with DATABASE_TYPE switching.

Runtime uses async SQLAlchemy (aiosqlite / asyncpg). Alembic migrations use a
sync engine derived from the same URL (see `to_sync_url`).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def to_async_url(url: str, database_type: str) -> str:
    """Normalize a DATABASE_URL for the async driver matching `database_type`."""
    parsed = make_url(url)
    if database_type == "sqlite":
        # Accept sqlite:// and sqlite+aiosqlite://
        if parsed.drivername in {"sqlite", "sqlite+pysqlite"}:
            parsed = parsed.set(drivername="sqlite+aiosqlite")
        elif not parsed.drivername.startswith("sqlite"):
            raise ValueError(
                f"DATABASE_TYPE=sqlite but DATABASE_URL uses driver "
                f"{parsed.drivername!r}"
            )
    elif database_type == "postgresql":
        # Accept postgresql://, postgres://, postgresql+asyncpg://, +psycopg
        if parsed.drivername in {
            "postgresql",
            "postgres",
            "postgresql+psycopg",
            "postgresql+psycopg2",
        }:
            parsed = parsed.set(drivername="postgresql+asyncpg")
        elif parsed.drivername != "postgresql+asyncpg":
            raise ValueError(
                f"DATABASE_TYPE=postgresql but DATABASE_URL uses driver "
                f"{parsed.drivername!r}"
            )
    else:
        raise ValueError(f"Unsupported DATABASE_TYPE: {database_type!r}")
    return parsed.render_as_string(hide_password=False)


def to_sync_url(url: str, database_type: str) -> str:
    """Normalize a DATABASE_URL for the sync driver (Alembic / fixtures)."""
    parsed = make_url(url)
    if database_type == "sqlite":
        if parsed.drivername.startswith("sqlite"):
            parsed = parsed.set(drivername="sqlite")
        else:
            raise ValueError(
                f"DATABASE_TYPE=sqlite but DATABASE_URL uses driver "
                f"{parsed.drivername!r}"
            )
    elif database_type == "postgresql":
        if parsed.drivername.startswith("postgresql") or parsed.drivername == "postgres":
            # Prefer psycopg3 (installed as psycopg[binary])
            parsed = parsed.set(drivername="postgresql+psycopg")
        else:
            raise ValueError(
                f"DATABASE_TYPE=postgresql but DATABASE_URL uses driver "
                f"{parsed.drivername!r}"
            )
    else:
        raise ValueError(f"Unsupported DATABASE_TYPE: {database_type!r}")
    return parsed.render_as_string(hide_password=False)


def _ensure_sqlite_parent_dir(url: str) -> None:
    """Create the parent directory for a file-backed SQLite database if needed."""
    parsed = make_url(url)
    # database is the path for sqlite URLs; skip :memory: and empty
    db_path = parsed.database
    if not db_path or db_path == ":memory:" or db_path.startswith("file:"):
        return
    # Absolute or relative path on disk
    path = Path(db_path)
    if path.parent and str(path.parent) not in {".", ""}:
        path.parent.mkdir(parents=True, exist_ok=True)


def _sqlite_connect_args(url: str) -> dict:
    """Return connect_args for SQLite (foreign keys, etc.)."""
    parsed = make_url(url)
    if parsed.database == ":memory:":
        # check_same_thread only matters for the default pysqlite driver;
        # aiosqlite ignores it but it's harmless.
        return {"check_same_thread": False}
    return {"check_same_thread": False}


def _enable_sqlite_foreign_keys(dbapi_conn, _connection_record) -> None:  # noqa: ANN001
    """PRAGMA foreign_keys=ON for every new SQLite connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ---------------------------------------------------------------------------
# Engine factories
# ---------------------------------------------------------------------------

def create_async_engine_from_settings(settings: Settings | None = None) -> AsyncEngine:
    """Build an async engine for the configured database backend."""
    settings = settings or get_settings()
    url = to_async_url(settings.DATABASE_URL, settings.DATABASE_TYPE)
    kwargs: dict = {"echo": settings.LOG_LEVEL == "debug", "pool_pre_ping": True}

    if settings.is_sqlite:
        _ensure_sqlite_parent_dir(url)
        kwargs["connect_args"] = _sqlite_connect_args(url)
        # StaticPool is preferred for :memory: so all connections share one DB
        parsed = make_url(url)
        if parsed.database == ":memory:":
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool

    engine = create_async_engine(url, **kwargs)

    if settings.is_sqlite:
        # Attach FK pragma on the underlying sync engine
        event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)

    return engine


def create_sync_engine_from_settings(settings: Settings | None = None) -> Engine:
    """Build a sync engine (Alembic, dual-DB fixtures, simple scripts)."""
    settings = settings or get_settings()
    url = to_sync_url(settings.DATABASE_URL, settings.DATABASE_TYPE)
    kwargs: dict = {"echo": settings.LOG_LEVEL == "debug", "pool_pre_ping": True}

    if settings.is_sqlite:
        _ensure_sqlite_parent_dir(url)
        kwargs["connect_args"] = _sqlite_connect_args(url)
        parsed = make_url(url)
        if parsed.database == ":memory:":
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool

    engine = create_engine(url, **kwargs)

    if settings.is_sqlite:
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)

    return engine


def create_engine_for(
    url: str,
    *,
    database_type: str | None = None,
    async_: bool = False,
) -> Engine | AsyncEngine:
    """Create an engine for an explicit URL (used by tests / tooling).

    `database_type` is inferred from the URL scheme when omitted.
    """
    if database_type is None:
        driver = make_url(url).drivername
        if driver.startswith("sqlite"):
            database_type = "sqlite"
        elif driver.startswith("postgresql") or driver.startswith("postgres"):
            database_type = "postgresql"
        else:
            raise ValueError(f"Cannot infer database type from URL driver {driver!r}")

    settings = Settings(
        DATABASE_TYPE=database_type,  # type: ignore[arg-type]
        DATABASE_URL=url,
        SECRET_KEY="test-secret-key-not-for-production",
    )
    if async_:
        return create_async_engine_from_settings(settings)
    return create_sync_engine_from_settings(settings)


# ---------------------------------------------------------------------------
# Session factories (module-level, lazy-bound to default settings)
# ---------------------------------------------------------------------------

_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""
    global _async_engine, _async_session_factory
    if _async_engine is None:
        _async_engine = create_async_engine_from_settings()
        _async_session_factory = async_sessionmaker(
            _async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async session factory."""
    get_async_engine()  # ensure initialized
    assert _async_session_factory is not None
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession and closes it."""
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


def reset_engine() -> None:
    """Drop cached engine/session factory (tests that reconfigure DB)."""
    global _async_engine, _async_session_factory
    _async_engine = None
    _async_session_factory = None


def make_sync_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a sync sessionmaker bound to `engine` (fixtures / Alembic helpers)."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
