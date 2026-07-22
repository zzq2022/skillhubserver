"""Unit tests for AgentWork-compatible JWT helpers."""

from __future__ import annotations

import pytest

from app.config import Settings, clear_settings_cache
from app.utils.jwt_tokens import decode_token, issue_token_pair


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-jwt-32bytes!!")
    monkeypatch.setenv("DATABASE_TYPE", "sqlite")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    clear_settings_cache()
    return Settings()


def test_issue_and_decode_access(settings: Settings) -> None:
    pair = issue_token_pair("user-123", settings)
    assert pair.access_token
    assert pair.refresh_token
    assert pair.access_token_expires_in == 3600
    assert pair.refresh_token_expires_in == 604800

    access = decode_token(pair.access_token, settings, expected_type="access")
    assert access["sub"] == "user-123"
    assert access["tokenType"] == "access"

    refresh = decode_token(pair.refresh_token, settings, expected_type="refresh")
    assert refresh["sub"] == "user-123"
    assert refresh["tokenType"] == "refresh"


def test_wrong_type_rejected(settings: Settings) -> None:
    pair = issue_token_pair("user-123", settings)
    with pytest.raises(ValueError):
        decode_token(pair.access_token, settings, expected_type="refresh")
    with pytest.raises(ValueError):
        decode_token(pair.refresh_token, settings, expected_type="access")


def test_invalid_token_rejected(settings: Settings) -> None:
    with pytest.raises(ValueError):
        decode_token("not.a.jwt", settings, expected_type="access")
