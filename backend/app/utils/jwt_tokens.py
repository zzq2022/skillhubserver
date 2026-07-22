"""JWT access/refresh tokens for AgentWork-compatible Hope clients."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt

from app.config import Settings

TOKEN_ISSUER = "skillhubserver"
ACCESS_AUDIENCE = "skillhub-api"
REFRESH_AUDIENCE = "skillhub-refresh"

# Hope / AgentWork-style defaults
ACCESS_TOKEN_TTL_SECONDS = 60 * 60  # 1 hour
REFRESH_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_token_expires_in: int
    refresh_token_expires_in: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def issue_token_pair(user_id: str, settings: Settings) -> TokenPair:
    now = _utcnow()
    access = jwt.encode(
        {
            "iss": TOKEN_ISSUER,
            "aud": ACCESS_AUDIENCE,
            "sub": user_id,
            "tokenType": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)).timestamp()),
            "jti": secrets.token_hex(16),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    refresh = jwt.encode(
        {
            "iss": TOKEN_ISSUER,
            "aud": REFRESH_AUDIENCE,
            "sub": user_id,
            "tokenType": "refresh",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)).timestamp()),
            "jti": secrets.token_hex(16),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        access_token_expires_in=ACCESS_TOKEN_TTL_SECONDS,
        refresh_token_expires_in=REFRESH_TOKEN_TTL_SECONDS,
    )


def decode_token(
    token: str,
    settings: Settings,
    *,
    expected_type: Literal["access", "refresh"],
) -> dict[str, Any]:
    audience = ACCESS_AUDIENCE if expected_type == "access" else REFRESH_AUDIENCE
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            audience=audience,
            issuer=TOKEN_ISSUER,
        )
    except jwt.PyJWTError as exc:
        raise ValueError("invalid token") from exc
    if payload.get("tokenType") != expected_type:
        raise ValueError("wrong token type")
    if not payload.get("sub"):
        raise ValueError("missing subject")
    return payload
