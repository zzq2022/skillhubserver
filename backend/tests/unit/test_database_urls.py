"""Unit tests for database URL normalization helpers (T1.2)."""

from __future__ import annotations

import pytest

from app.database import to_async_url, to_sync_url


def test_sqlite_to_async() -> None:
    assert to_async_url("sqlite:///./data/db/app.db", "sqlite") == "sqlite+aiosqlite:///./data/db/app.db"
    assert (
        to_async_url("sqlite+aiosqlite:///:memory:", "sqlite")
        == "sqlite+aiosqlite:///:memory:"
    )


def test_sqlite_to_sync() -> None:
    assert to_sync_url("sqlite+aiosqlite:///./x.db", "sqlite") == "sqlite:///./x.db"


def test_postgresql_to_async() -> None:
    url = to_async_url("postgresql://user:pass@localhost:5432/db", "postgresql")
    assert url.startswith("postgresql+asyncpg://")
    assert "user:pass@localhost:5432/db" in url


def test_postgresql_to_sync() -> None:
    url = to_sync_url("postgresql+asyncpg://user:pass@host/db", "postgresql")
    assert url.startswith("postgresql+psycopg://")


def test_mismatched_type_raises() -> None:
    with pytest.raises(ValueError):
        to_async_url("postgresql://u:p@h/db", "sqlite")
    with pytest.raises(ValueError):
        to_async_url("sqlite:///x.db", "postgresql")
