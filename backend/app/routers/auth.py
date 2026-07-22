"""Auth endpoints: login / logout / me / password."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.middleware.session_auth import CurrentUser
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginData,
    LoginRequest,
    UserPublic,
)
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(
    response: Response,
    settings: Settings,
    session_id: str,
) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # set True behind HTTPS reverse proxy in production
        path="/",
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = AuthService(db, settings)
    result = await service.login_async(body.username, body.password)
    _set_session_cookie(response, settings, result.session_id)
    data = LoginData(
        user=UserPublic.model_validate(result.user),
        csrf_token=result.csrf_token,
    )
    return {"data": data.model_dump(by_alias=True)}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if session_id:
        service = AuthService(db, settings)
        await service.logout_async(session_id)
    _clear_session_cookie(response, settings)
    return {"data": {"ok": True}}


@router.get("/me")
async def me(request: Request, user: CurrentUser) -> dict:
    # Flatten user fields (backward compatible) + optional csrfToken for SPA reload.
    payload = UserPublic.model_validate(user).model_dump(by_alias=True)
    session_row = getattr(request.state, "session_row", None)
    if session_row is not None and getattr(session_row, "csrf_token", None):
        payload["csrfToken"] = session_row.csrf_token
    return {"data": payload}


@router.put("/password")
async def change_password(
    body: ChangePasswordRequest,
    user: CurrentUser,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = AuthService(db, settings)
    await service.change_password_async(user, body.current_password, body.new_password)
    # All sessions revoked — clear cookie so client re-logs in.
    _clear_session_cookie(response, settings)
    return {"data": {"ok": True}}
