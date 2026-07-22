"""Shared pytest fixtures.

Dual-database matrix (design.md §9.1):
- SQLite is always available (file under tmp_path or :memory:).
- PostgreSQL is optional. Set TEST_POSTGRESQL_URL (e.g.
  postgresql+psycopg://test:test@localhost:5433/test) to include it in the
  parameterized fixtures; otherwise postgresql params are skipped.
"""

from __future__ import annotations

import os
from collections.abc import Generator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from app.database import create_engine_for, make_sync_session_factory

# Backend root (parent of tests/) — used to locate alembic.ini
BACKEND_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

EXPECTED_TABLES = {
    "users",
    "sessions",
    "skills",
    "skill_versions",
    "reviews",
    "media",
    "skill_stars",
    "alembic_version",
}


def _postgresql_url() -> str | None:
    return os.environ.get("TEST_POSTGRESQL_URL") or os.environ.get("TEST_DATABASE_URL_POSTGRESQL")


def _can_connect_postgresql(url: str) -> bool:
    try:
        engine = create_engine_for(url, database_type="postgresql", async_=False)
        assert isinstance(engine, Engine)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "postgresql: test requires a live PostgreSQL (set TEST_POSTGRESQL_URL)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip postgresql-parametrized tests when no PG is available."""
    pg_url = _postgresql_url()
    pg_ok = bool(pg_url) and _can_connect_postgresql(pg_url) if pg_url else False
    if pg_ok:
        return

    skip_pg = pytest.mark.skip(
        reason="PostgreSQL not available (set TEST_POSTGRESQL_URL to enable dual-DB matrix)"
    )
    for item in items:
        # Only skip the dual-DB fixture param id "[postgresql]", not unit tests
        # whose names merely contain the word "postgresql".
        if "[postgresql]" in item.nodeid:
            item.add_marker(skip_pg)


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    """Alembic Config pointed at backend/alembic.ini."""
    cfg = Config(str(ALEMBIC_INI))
    # script_location is relative to cwd; force absolute
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


@pytest.fixture(params=["sqlite", "postgresql"])
def db_engine(request: pytest.FixtureRequest, tmp_path: Path) -> Generator[Engine, None, None]:
    """Sync engine for the requested database backend, with Alembic migrations applied.

    Yields a fresh, migrated engine. Tears down tables (PG) or deletes the file
    (SQLite) after the test.
    """
    backend = request.param
    previous_env = {
        "DATABASE_TYPE": os.environ.get("DATABASE_TYPE"),
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
    }

    if backend == "sqlite":
        db_file = tmp_path / "test.db"
        url = f"sqlite:///{db_file}"
    else:
        pg_url = _postgresql_url()
        if not pg_url:
            pytest.skip("TEST_POSTGRESQL_URL not set")
        url = pg_url

    os.environ["DATABASE_TYPE"] = backend
    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

    # Clear Settings cache so Alembic env / app code see the new env.
    from app.config import clear_settings_cache

    clear_settings_cache()

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)

    # Run migrations online via env.py (reads DATABASE_* from os.environ)
    command.upgrade(cfg, "head")

    engine = create_engine_for(url, database_type=backend, async_=False)
    assert isinstance(engine, Engine)

    try:
        yield engine
    finally:
        engine.dispose()
        # Downgrade so the next test (or PG shared DB) starts clean.
        try:
            command.downgrade(cfg, "base")
        except Exception:
            # Best-effort cleanup for shared PG databases.
            if backend == "postgresql":
                try:
                    from app.database import Base
                    import app.models  # noqa: F401

                    Base.metadata.drop_all(bind=create_engine_for(url, database_type="postgresql"))
                except Exception:
                    pass

        # Restore previous env
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        clear_settings_cache()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Yield a SQLAlchemy Session bound to the dual-DB engine fixture."""
    factory = make_sync_session_factory(db_engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    """SQLite-only engine with migrations applied (fast unit/integration helpers)."""
    db_file = tmp_path / "sqlite_only.db"
    url = f"sqlite:///{db_file}"

    previous = {
        "DATABASE_TYPE": os.environ.get("DATABASE_TYPE"),
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
    }
    os.environ["DATABASE_TYPE"] = "sqlite"
    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

    from app.config import clear_settings_cache

    clear_settings_cache()

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")

    engine = create_engine_for(url, database_type="sqlite", async_=False)
    assert isinstance(engine, Engine)
    try:
        yield engine
    finally:
        engine.dispose()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        clear_settings_cache()
