"""Bearer JWT authentication for AgentWork-compatible clients (Hope)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthError, NotAuthenticated, UserDisabled
from app.utils.jwt_tokens import decode_token


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization") or request.headers.get("authorization")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


async def get_user_from_bearer(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User | None:
    token = _extract_bearer(request)
    if not token:
        return None
    try:
        payload = decode_token(token, settings, expected_type="access")
    except ValueError:
        return None
    user = await UserRepository(db).get_by_id_async(payload["sub"])
    if user is None or not user.is_active:
        return None
    request.state.user = user
    request.state.auth_via = "bearer"
    return user


async def require_bearer_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    token = _extract_bearer(request)
    if not token:
        raise NotAuthenticated()
    try:
        payload = decode_token(token, settings, expected_type="access")
    except ValueError as exc:
        raise AuthError("invalid_token", "Invalid or expired access token", 401) from exc
    user = await UserRepository(db).get_by_id_async(payload["sub"])
    if user is None:
        raise NotAuthenticated()
    if not user.is_active:
        raise UserDisabled()
    request.state.user = user
    request.state.auth_via = "bearer"
    return user


BearerUser = Annotated[User, Depends(require_bearer_user)]
OptionalBearerUser = Annotated[User | None, Depends(get_user_from_bearer)]
