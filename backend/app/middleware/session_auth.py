"""Session authentication FastAPI dependencies.

Extract session id from Cookie, validate against the sessions table, enforce
active user, apply sliding idle timeout, and inject the current user.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User, UserRole
from app.services.auth_service import AuthError, AuthService


async def get_optional_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User | None:
    """Return the current user if a valid session cookie is present, else None."""
    cookie_name = settings.SESSION_COOKIE_NAME
    session_id = request.cookies.get(cookie_name)
    if not session_id:
        return None
    service = AuthService(db, settings)
    try:
        user, session_row = await service.get_current_user_async(session_id)
    except AuthError:
        return None
    # Stash for CSRF middleware / handlers that need the raw session row.
    request.state.user = user
    request.state.session_row = session_row
    request.state.session_id = session_id
    return user


async def require_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Require a valid authenticated session; raise AuthError otherwise."""
    cookie_name = settings.SESSION_COOKIE_NAME
    session_id = request.cookies.get(cookie_name)
    service = AuthService(db, settings)
    try:
        user, session_row = await service.get_current_user_async(session_id)
    except AuthError as exc:
        raise exc
    request.state.user = user
    request.state.session_row = session_row
    request.state.session_id = session_id
    return user


async def require_admin(user: Annotated[User, Depends(require_user)]) -> User:
    """Require the authenticated user to have the admin role."""
    if user.role != UserRole.ADMIN:
        raise AuthError("forbidden", "Admin privileges required", 403)
    return user


def auth_error_response(exc: AuthError) -> JSONResponse:
    """Map AuthError to the standard error envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


# Type aliases for route signatures
CurrentUser = Annotated[User, Depends(require_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(require_admin)]
