"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.middleware.csrf import CSRFError, CSRFMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import (
    admin,
    auth,
    bootstrap,
    compat_auth,
    compat_skillhub,
    import_export,
    media,
    skillhub,
    skills,
)
from app.services.auth_service import AuthError

# Docker copies frontend dist to /app/static; local/dev may use repo frontend/dist.
_STATIC_CANDIDATES = (
    Path("/app/static"),
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
    Path(__file__).resolve().parent.parent / "static",
)


def resolve_static_dir() -> Path | None:
    for candidate in _STATIC_CANDIDATES:
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Eagerly validate settings at startup (fail fast if SECRET_KEY missing).
    get_settings()
    # Periodic expired-session cleanup (T10.3).
    from app.services.session_cleanup import start_session_cleanup_task

    cleanup_task, cleanup_stop = start_session_cleanup_task(interval_seconds=3600)
    # Opportunistic cleanup once at startup.
    try:
        from app.services.session_cleanup import cleanup_expired_sessions_once

        await cleanup_expired_sessions_once()
    except Exception:  # noqa: BLE001
        pass

    yield

    cleanup_stop.set()
    cleanup_task.cancel()
    try:
        await cleanup_task
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        pass
    from app.database import reset_engine

    reset_engine()


app = FastAPI(
    title="SkillHub Server",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware order: last added runs first on request.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)

# API routers under /api/v1 (browser Session + CSRF)
app.include_router(bootstrap.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(skills.router, prefix="/api/v1")
app.include_router(import_export.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(skillhub.router, prefix="/api/v1")

# AgentWork-compatible surface for Hope (Bearer JWT, no /v1 prefix)
app.include_router(compat_auth.router, prefix="/api")
app.include_router(compat_skillhub.router, prefix="/api")


@app.exception_handler(AuthError)
async def auth_error_handler(_request: Request, exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(CSRFError)
async def csrf_error_handler(_request: Request, exc: CSRFError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.get("/api/v1/health")
def health() -> dict:
    return {"data": {"status": "ok"}}


# ---- Static SPA hosting (T10.2) ---------------------------------------------
_static_dir = resolve_static_dir()
if _static_dir is not None:
    # Assets with hashed filenames under /assets (Vite default)
    assets = _static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/", response_model=None)
    async def spa_index() -> FileResponse:
        return FileResponse(_static_dir / "index.html")

    @app.get("/{full_path:path}", response_model=None)
    async def spa_fallback(full_path: str) -> FileResponse | JSONResponse:
        # Never swallow API routes (already registered above); this is last-resort.
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "not_found", "message": "Not found"}},
            )
        candidate = (_static_dir / full_path).resolve()
        try:
            candidate.relative_to(_static_dir.resolve())
        except ValueError:
            return FileResponse(_static_dir / "index.html")
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_static_dir / "index.html")
else:

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "SkillHub Server"}
