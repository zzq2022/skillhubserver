"""Auth integration tests (T2.9).

Covers: bootstrap init, login/logout, /me, session expiry, CSRF rejection,
disabled-user immediate invalidation, change password.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, clear_settings_cache
from app.database import Base, get_db, reset_engine, to_async_url
from app.main import app
from app.models import Session as SessionModel
from app.models import User, UserRole
from app.utils.password import hash_password

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

TEST_SECRET = "test-secret-key-for-auth-integration"


@pytest.fixture
def auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    """Configure env + migrations for an isolated SQLite file DB used by the app."""
    db_file = tmp_path / "auth.db"
    url = f"sqlite:///{db_file}"

    monkeypatch.setenv("DATABASE_TYPE", "sqlite")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("SESSION_MAX_AGE", "604800")
    monkeypatch.setenv("SESSION_IDLE_TIMEOUT", "1800")
    clear_settings_cache()
    reset_engine()

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")

    yield url

    reset_engine()
    clear_settings_cache()


@pytest.fixture
async def client(auth_env: str) -> AsyncIterator[AsyncClient]:
    """httpx AsyncClient bound to the FastAPI app with DB dependency override."""
    async_url = to_async_url(auth_env, "sqlite")
    engine = create_async_engine(
        async_url,
        connect_args={"check_same_thread": False},
    )

    # Enable FK pragma for aiosqlite
    @event.listens_for(engine.sync_engine, "connect")
    def _fk(dbapi_conn, _rec):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _override_get_db

    # Point process-wide engine at the same DB so CSRF middleware shares it.
    import app.database as database_mod

    database_mod._async_engine = engine
    database_mod._async_session_factory = factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()
    reset_engine()


def _sync_session(url: str) -> Session:
    engine = create_engine(url)
    return sessionmaker(bind=engine, expire_on_commit=False)()


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bootstrap_status_uninitialized(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/bootstrap")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["initialized"] is False
    assert body["registrationClosed"] is False


@pytest.mark.asyncio
async def test_bootstrap_init_creates_admin_and_logs_in(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/bootstrap/init",
        json={"username": "admin", "password": "adminpass1"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"
    assert "csrfToken" in data
    assert "session_id" in resp.cookies or client.cookies.get("session_id")

    # Second init is rejected
    resp2 = await client.post(
        "/api/v1/bootstrap/init",
        json={"username": "other", "password": "adminpass1"},
    )
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "already_initialized"


# ---------------------------------------------------------------------------
# Login / logout / me
# ---------------------------------------------------------------------------


async def _bootstrap(client: AsyncClient, username: str = "admin", password: str = "adminpass1") -> dict:
    resp = await client.post(
        "/api/v1/bootstrap/init",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_login_logout_me(client: AsyncClient) -> None:
    await _bootstrap(client)
    # Clear cookies so we exercise login explicitly
    client.cookies.clear()

    bad = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"

    ok = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "adminpass1"},
    )
    assert ok.status_code == 200
    csrf = ok.json()["data"]["csrfToken"]
    assert csrf

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "admin"

    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf},
    )
    assert logout.status_code == 200

    me2 = await client.get("/api/v1/auth/me")
    assert me2.status_code == 401


@pytest.mark.asyncio
async def test_login_case_insensitive_username(client: AsyncClient) -> None:
    await _bootstrap(client, username="AdminUser")
    client.cookies.clear()
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "adminuser", "password": "adminpass1"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["user"]["username"] == "AdminUser"


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_csrf_rejects_write_without_token(client: AsyncClient) -> None:
    data = await _bootstrap(client)
    # Bootstrap already set the session cookie. Change password is a write.
    resp = await client.put(
        "/api/v1/auth/password",
        json={"current_password": "adminpass1", "new_password": "newpassword1"},
        # deliberately omit X-CSRF-Token
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "csrf_failed"

    # Wrong token also fails
    resp2 = await client.put(
        "/api/v1/auth/password",
        json={"current_password": "adminpass1", "new_password": "newpassword1"},
        headers={"X-CSRF-Token": "0" * 64},
    )
    assert resp2.status_code == 403

    # Correct token succeeds
    resp3 = await client.put(
        "/api/v1/auth/password",
        json={"current_password": "adminpass1", "new_password": "newpassword1"},
        headers={"X-CSRF-Token": data["csrfToken"]},
    )
    assert resp3.status_code == 200, resp3.text


# ---------------------------------------------------------------------------
# Disabled user / session expiry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_user_session_invalidated(
    client: AsyncClient,
    auth_env: str,
) -> None:
    data = await _bootstrap(client)
    # Confirm session works
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200

    # Disable the user directly in the DB
    sync = _sync_session(auth_env)
    try:
        user = sync.query(User).filter(User.username == "admin").one()
        user.is_active = False
        sync.commit()
    finally:
        sync.close()

    me2 = await client.get("/api/v1/auth/me")
    assert me2.status_code in {401, 403}
    body = me2.json()["error"]
    assert body["code"] in {"user_disabled", "not_authenticated", "session_expired"}


@pytest.mark.asyncio
async def test_session_absolute_expiry(
    client: AsyncClient,
    auth_env: str,
) -> None:
    await _bootstrap(client)
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200

    # Force-expire the session in the DB
    sync = _sync_session(auth_env)
    try:
        row = sync.query(SessionModel).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        sync.commit()
    finally:
        sync.close()

    me2 = await client.get("/api/v1/auth/me")
    assert me2.status_code == 401
    assert me2.json()["error"]["code"] in {"session_expired", "not_authenticated"}


@pytest.mark.asyncio
async def test_session_idle_timeout(
    client: AsyncClient,
    auth_env: str,
) -> None:
    await _bootstrap(client)

    sync = _sync_session(auth_env)
    try:
        row = sync.query(SessionModel).one()
        row.last_active_at = datetime.now(timezone.utc) - timedelta(hours=1)
        sync.commit()
    finally:
        sync.close()

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_me_without_cookie(client: AsyncClient) -> None:
    await _bootstrap(client)
    client.cookies.clear()
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
