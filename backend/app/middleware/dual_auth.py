"""Accept either Bearer JWT (Hope) or session cookie (browser Web UI)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.middleware.bearer_auth import get_user_from_bearer
from app.models.user import User
from app.services.auth_service import AuthService, NotAuthenticated


async def require_dual_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Prefer Bearer JWT; fall back to session cookie."""
    user = await get_user_from_bearer(request, db, settings)
    if user is not None:
        return user

    cookie_name = settings.SESSION_COOKIE_NAME
    session_id = request.cookies.get(cookie_name)
    if not session_id:
        raise NotAuthenticated()
    service = AuthService(db, settings)
    user, session_row = await service.get_current_user_async(session_id)
    request.state.user = user
    request.state.session_row = session_row
    request.state.auth_via = "session"
    return user


async def optional_dual_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User | None:
    user = await get_user_from_bearer(request, db, settings)
    if user is not None:
        return user
    cookie_name = settings.SESSION_COOKIE_NAME
    session_id = request.cookies.get(cookie_name)
    if not session_id:
        return None
    try:
        service = AuthService(db, settings)
        user, session_row = await service.get_current_user_async(session_id)
        request.state.user = user
        request.state.session_row = session_row
        request.state.auth_via = "session"
        return user
    except Exception:
        return None


DualUser = Annotated[User, Depends(require_dual_user)]
OptionalDualUser = Annotated[User | None, Depends(optional_dual_user)]
