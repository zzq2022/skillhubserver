"""Unit tests for app.config.Settings (T1.1)."""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from app.config import Settings, clear_settings_cache, get_settings


@pytest.fixture(autouse=True)
def _clean_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_settings_cache()
    # Ensure required SECRET_KEY for tests that construct Settings freely
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key")
    yield
    clear_settings_cache()


def test_default_sqlite_settings() -> None:
    s = Settings(SECRET_KEY="abc")  # type: ignore[call-arg]
    assert s.DATABASE_TYPE == "sqlite"
    assert s.is_sqlite is True
    assert s.is_postgresql is False
    assert s.SESSION_MAX_AGE == 604_800
    assert s.SESSION_IDLE_TIMEOUT == 1_800
    assert s.MAX_UPLOAD_SIZE == 5_242_880


def test_database_type_normalization() -> None:
    s = Settings(SECRET_KEY="abc", DATABASE_TYPE="PostgreSQL")  # type: ignore[call-arg]
    assert s.DATABASE_TYPE == "postgresql"
    assert s.is_postgresql is True


def test_secret_key_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    clear_settings_cache()
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "cached-key")
    clear_settings_cache()
    a = get_settings()
    b = get_settings()
    assert a is b
