"""Unit tests for Argon2id password helpers (T2.1)."""

from __future__ import annotations

import pytest

from app.utils.password import hash_password, needs_rehash, verify_password


def test_hash_and_verify() -> None:
    h = hash_password("s3cret-pass")
    assert h.startswith("$argon2")
    assert verify_password(h, "s3cret-pass") is True
    assert verify_password(h, "wrong") is False


def test_empty_password_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("")


def test_verify_empty_or_garbage() -> None:
    assert verify_password("", "x") is False
    assert verify_password("not-a-hash", "x") is False
    assert verify_password(hash_password("a"), "") is False


def test_needs_rehash_current() -> None:
    h = hash_password("ok")
    assert needs_rehash(h) is False
