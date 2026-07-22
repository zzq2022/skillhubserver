"""CSRF double-submit token validation for write methods.

Session Cookie is SameSite=Lax. After login the server returns a csrfToken in
the JSON body; the frontend stores it in memory and echoes it as
`X-CSRF-Token` on POST/PUT/PATCH/DELETE. The server compares it to
`session.csrf_token`.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import Settings, get_settings
from app.database import get_async_session_factory
from app.services.auth_service import AuthService

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_HEADER = "X-CSRF-Token"
# Endpoints that establish a session (no prior CSRF token available) or are
# pre-auth setup. Authenticated writes still need CSRF everywhere else.
CSRF_EXEMPT_PATHS = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/bootstrap/init",
        # Hope / AgentWork token auth (no session CSRF yet)
        "/api/auth/login",
        "/api/auth/refresh",
    }
)


class CSRFError(Exception):
    def __init__(self, message: str = "CSRF token missing or invalid") -> None:
        super().__init__(message)
        self.code = "csrf_failed"
        self.message = message
        self.status_code = 403


def validate_csrf(session_csrf: str, header_value: str | None) -> None:
    """Raise CSRFError unless header matches the session token (constant-time)."""
    if not header_value or not session_csrf:
        raise CSRFError()
    if not secrets.compare_digest(session_csrf, header_value):
        raise CSRFError()


class CSRFMiddleware(BaseHTTPMiddleware):
    """Reject write requests that lack a matching X-CSRF-Token header.

    Only enforced when a session cookie is present (authenticated writes).
    Unauthenticated writes (login / bootstrap init) are allowed through;
    those endpoints do not require CSRF because there is no session yet.
    """

    def __init__(self, app: ASGIApp, settings: Settings | None = None) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method in SAFE_METHODS:
            return await call_next(request)

        # Pre-auth / session-establishing endpoints never require CSRF.
        if request.url.path in CSRF_EXEMPT_PATHS:
            return await call_next(request)

        # AgentWork-compatible surface for Hope uses Bearer JWT (or public
        # analytics posts). Never require browser double-submit CSRF here —
        # even if a session cookie happens to be present on the same client.
        path = request.url.path
        if path.startswith("/api/auth/") or path.startswith("/api/skillhub/"):
            return await call_next(request)

        # Bearer JWT on other paths also skips CSRF.
        auth_header = request.headers.get("Authorization") or ""
        if auth_header.lower().startswith("bearer "):
            return await call_next(request)

        settings = self._settings or get_settings()
        cookie_name = settings.SESSION_COOKIE_NAME
        session_id = request.cookies.get(cookie_name)

        # No session cookie → not an authenticated write; skip CSRF.
        if not session_id:
            return await call_next(request)

        # Load session to get csrf_token. Use a short-lived session so we don't
        # conflict with the request's own dependency-injected session.
        factory = get_async_session_factory()
        async with factory() as db:
            service = AuthService(db, settings)
            try:
                _user, session_row = await service.get_current_user_async(session_id)
            except Exception:
                # Let the route / require_user dependency surface the real auth error.
                return await call_next(request)

            header = request.headers.get(CSRF_HEADER)
            try:
                validate_csrf(session_row.csrf_token, header)
            except CSRFError as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"error": {"code": exc.code, "message": exc.message}},
                )

        return await call_next(request)


async def require_csrf(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Dependency alternative to middleware — use on individual write routes.

    Expects `request.state.session_row` to have been set by `require_user`.
    """
    session_row = getattr(request.state, "session_row", None)
    if session_row is None:
        # Unauthenticated path — nothing to check (login/bootstrap).
        return
    header = request.headers.get(CSRF_HEADER)
    validate_csrf(session_row.csrf_token, header)
