"""Argon2id password hashing helpers."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# OWASP-recommended parameters for Argon2id (argon2-cffi defaults are already
# sensible; we pin them explicitly so upgrades don't silently change cost).
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Return an Argon2id hash of `password`."""
    if not password:
        raise ValueError("password must not be empty")
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Return True if `password` matches `password_hash`.

    Never raises on mismatch; returns False. Rehash is left to callers that
    want to rotate parameters after a successful login.
    """
    if not password_hash or not password:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
    except Exception:
        return False


def needs_rehash(password_hash: str) -> bool:
    """Return True if the stored hash should be upgraded to current parameters."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:
        return False
