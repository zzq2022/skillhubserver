"""AgentWork-compatible auth surface for Hope: /api/auth/login|refresh.

Returns accessToken/refreshToken (Bearer) instead of session cookies.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.repositories.user_repo import UserRepository
from app.services.auth_service import (
    AuthError,
    InvalidCredentials,
    NotAuthenticated,
    UserDisabled,
)
from app.utils.jwt_tokens import decode_token, issue_token_pair
from app.utils.password import needs_rehash, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["compat-auth"])


class CompatLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=256)
    # Hope may send captcha fields; ignore if present
    captchaId: str | None = None
    captchaAnswer: str | None = None


class CompatRefreshRequest(BaseModel):
    refreshToken: str | None = None


def _user_payload(user: Any) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "displayName": user.username,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }


def _token_data(user: Any, pair: Any) -> dict[str, Any]:
    # Hope CloudLoginResponse expects camelCase accessToken/refreshToken/user
    return {
        "user": _user_payload(user),
        "accessToken": pair.access_token,
        "refreshToken": pair.refresh_token,
        "accessTokenExpiresIn": pair.access_token_expires_in,
        "refreshTokenExpiresIn": pair.refresh_token_expires_in,
    }


@router.post("/login")
async def compat_login(
    body: CompatLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    # Validate credentials without creating a browser session cookie.
    users = UserRepository(db)
    user = await users.get_by_username_async(body.username)

    if user is None or not verify_password(user.password_hash, body.password):
        raise InvalidCredentials()
    if not user.is_active:
        raise UserDisabled()

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
        await db.commit()

    pair = issue_token_pair(user.id, settings)
    return {"data": _token_data(user, pair)}


@router.post("/refresh")
async def compat_refresh(
    body: CompatRefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if not body.refreshToken:
        raise AuthError("validation_error", "refreshToken is required", 422)
    try:
        payload = decode_token(body.refreshToken, settings, expected_type="refresh")
    except ValueError as exc:
        raise AuthError("invalid_token", "Invalid or expired refresh token", 401) from exc

    user = await UserRepository(db).get_by_id_async(payload["sub"])
    if user is None:
        raise NotAuthenticated()
    if not user.is_active:
        raise UserDisabled()

    pair = issue_token_pair(user.id, settings)
    return {"data": _token_data(user, pair)}
