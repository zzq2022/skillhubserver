"""Admin user-management integration tests (T3.3)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import clear_settings_cache
from app.database import get_db, reset_engine, to_async_url
from app.main import app
from app.models import Session as SessionModel
from app.models import User

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
TEST_SECRET = "test-secret-key-for-admin-integration"


@pytest.fixture
def admin_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    db_file = tmp_path / "admin.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_TYPE", "sqlite")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    clear_settings_cache()
    reset_engine()

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")
    yield url
    reset_engine()
    clear_settings_cache()


@pytest.fixture
async def client(admin_env: str) -> AsyncIterator[AsyncClient]:
    async_url = to_async_url(admin_env, "sqlite")
    engine = create_async_engine(async_url, connect_args={"check_same_thread": False})

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
    import app.database as database_mod

    database_mod._async_engine = engine
    database_mod._async_session_factory = factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()
    reset_engine()


async def _bootstrap_admin(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/bootstrap/init",
        json={"username": "admin", "password": "adminpass1"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _csrf(data: dict) -> dict[str, str]:
    return {"X-CSRF-Token": data["csrfToken"]}


@pytest.mark.asyncio
async def test_create_list_users(client: AsyncClient) -> None:
    data = await _bootstrap_admin(client)

    created = await client.post(
        "/api/v1/admin/users",
        json={"username": "alice", "password": "alicepass1", "role": "user"},
        headers=_csrf(data),
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    assert body["username"] == "alice"
    assert body["role"] == "user"
    assert body["isActive"] is True

    listed = await client.get("/api/v1/admin/users")
    assert listed.status_code == 200
    names = {u["username"] for u in listed.json()["data"]}
    assert names == {"admin", "alice"}


@pytest.mark.asyncio
async def test_role_change_and_last_admin_protection(client: AsyncClient) -> None:
    data = await _bootstrap_admin(client)

    # Create a second admin
    r = await client.post(
        "/api/v1/admin/users",
        json={"username": "admin2", "password": "adminpass2", "role": "admin"},
        headers=_csrf(data),
    )
    assert r.status_code == 201
    admin2_id = r.json()["data"]["id"]

    # Demote admin2 → user: ok (admin remains)
    demote = await client.put(
        f"/api/v1/admin/users/{admin2_id}/role",
        json={"role": "user"},
        headers=_csrf(data),
    )
    assert demote.status_code == 200
    assert demote.json()["data"]["role"] == "user"

    # Promote back
    promote = await client.put(
        f"/api/v1/admin/users/{admin2_id}/role",
        json={"role": "admin"},
        headers=_csrf(data),
    )
    assert promote.status_code == 200

    # Get the first admin's id and try to demote the only remaining path:
    # first demote admin2 again, then try demoting the last admin.
    await client.put(
        f"/api/v1/admin/users/{admin2_id}/role",
        json={"role": "user"},
        headers=_csrf(data),
    )
    me = await client.get("/api/v1/auth/me")
    admin_id = me.json()["data"]["id"]
    last = await client.put(
        f"/api/v1/admin/users/{admin_id}/role",
        json={"role": "user"},
        headers=_csrf(data),
    )
    assert last.status_code == 400
    assert last.json()["error"]["code"] == "last_admin_protected"


@pytest.mark.asyncio
async def test_disable_user_invalidates_session(
    client: AsyncClient,
    admin_env: str,
) -> None:
    data = await _bootstrap_admin(client)

    # Create a regular user
    r = await client.post(
        "/api/v1/admin/users",
        json={"username": "bob", "password": "bobpass12", "role": "user"},
        headers=_csrf(data),
    )
    bob_id = r.json()["data"]["id"]

    # Login as bob in a separate client jar
    bob_client_transport = ASGITransport(app=app)
    async with AsyncClient(transport=bob_client_transport, base_url="http://test") as bob:
        login = await bob.post(
            "/api/v1/auth/login",
            json={"username": "bob", "password": "bobpass12"},
        )
        assert login.status_code == 200
        me = await bob.get("/api/v1/auth/me")
        assert me.status_code == 200

        # Admin disables bob
        disable = await client.put(
            f"/api/v1/admin/users/{bob_id}/status",
            json={"is_active": False},
            headers=_csrf(data),
        )
        assert disable.status_code == 200
        assert disable.json()["data"]["isActive"] is False

        # Bob's session is gone
        me2 = await bob.get("/api/v1/auth/me")
        assert me2.status_code in {401, 403}


@pytest.mark.asyncio
async def test_delete_last_admin_blocked(client: AsyncClient) -> None:
    data = await _bootstrap_admin(client)
    me = await client.get("/api/v1/auth/me")
    admin_id = me.json()["data"]["id"]

    resp = await client.delete(
        f"/api/v1/admin/users/{admin_id}",
        headers=_csrf(data),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "last_admin_protected"


@pytest.mark.asyncio
async def test_stats_endpoint(client: AsyncClient) -> None:
    data = await _bootstrap_admin(client)
    resp = await client.get("/api/v1/admin/stats")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["users"] == 1
    assert body["skills"] == 0
    assert body["publicSkills"] == 0
    assert body["pendingReviews"] == 0


@pytest.mark.asyncio
async def test_non_admin_forbidden(client: AsyncClient) -> None:
    data = await _bootstrap_admin(client)
    r = await client.post(
        "/api/v1/admin/users",
        json={"username": "carol", "password": "carolpass1", "role": "user"},
        headers=_csrf(data),
    )
    assert r.status_code == 201

    # Login as carol
    client.cookies.clear()
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "carol", "password": "carolpass1"},
    )
    assert login.status_code == 200

    forbidden = await client.get("/api/v1/admin/users")
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"
