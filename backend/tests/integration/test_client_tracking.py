"""Integration tests for client tracking and chat session auditing."""

from __future__ import annotations

from collections.abc import AsyncIterator, Generator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, clear_settings_cache
from app.database import Base, get_db, reset_engine, to_async_url
from app.main import app
from app.models import User, UserRole
from app.utils.jwt_tokens import issue_token_pair
from app.utils.password import hash_password

TEST_SECRET = "test-secret-key-for-client-tracking"


@pytest.fixture
def test_db_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    db_file = tmp_path / "tracking.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_TYPE", "sqlite")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    clear_settings_cache()
    reset_engine()

    yield url
    reset_engine()
    clear_settings_cache()


@pytest.fixture
async def async_client(test_db_env: str) -> AsyncIterator[AsyncClient]:
    async_url = to_async_url(test_db_env, "sqlite")
    engine = create_async_engine(async_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine.sync_engine, "connect")
    def _fk(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
            finally:
                await session.rollback()

    app.dependency_overrides[get_db] = _override_get_db

    async with factory() as session:
        admin_user = User(
            id="admin-user-id",
            username="admin",
            password_hash=hash_password("adminpass123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        norm_user = User(
            id="norm-user-id",
            username="developer",
            password_hash=hash_password("devpass123"),
            role=UserRole.USER,
            is_active=True,
        )
        session.add_all([admin_user, norm_user])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_client_heartbeat_and_admin_view(async_client: AsyncClient) -> None:
    hb_resp = await async_client.post(
        "/api/client/heartbeat",
        json={
            "instanceId": "ci_test_anon_001",
            "machineName": "DevPC-1",
            "osPlatform": "win32 (x64)",
            "appVersion": "0.0.3",
            "hostVersion": "DeepSeek Harness 0.2.1-alpha.2",
        },
    )
    assert hb_resp.status_code == 200
    hb_data = hb_resp.json()["data"]
    assert hb_data["status"] == "ok"
    assert hb_data["isOnline"] is True

    settings = Settings(SECRET_KEY=TEST_SECRET)
    tokens = issue_token_pair("norm-user-id", settings)
    auth_headers = {"Authorization": f"Bearer {tokens.access_token}"}

    hb_auth_resp = await async_client.post(
        "/api/client/heartbeat",
        headers=auth_headers,
        json={
            "instanceId": "ci_test_user_002",
            "machineName": "MacBook-Pro",
            "osPlatform": "darwin (arm64)",
            "appVersion": "0.0.3",
        },
    )
    assert hb_auth_resp.status_code == 200

    admin_tokens = issue_token_pair("admin-user-id", settings)
    admin_headers = {"Authorization": f"Bearer {admin_tokens.access_token}"}

    list_resp = await async_client.get("/api/v1/admin/clients", headers=admin_headers)
    assert list_resp.status_code == 200
    clients_data = list_resp.json()["data"]
    assert clients_data["totalCount"] == 2
    assert clients_data["onlineCount"] == 2

    items = clients_data["items"]
    assert any(c["id"] == "ci_test_anon_001" and c["username"] == "未登录" for c in items)
    assert any(c["id"] == "ci_test_user_002" and c["username"] == "developer" for c in items)


@pytest.mark.asyncio
async def test_session_sync_and_auditing(async_client: AsyncClient) -> None:
    settings = Settings(SECRET_KEY=TEST_SECRET)
    tokens = issue_token_pair("norm-user-id", settings)
    auth_headers = {"Authorization": f"Bearer {tokens.access_token}"}

    sync_payload = {
        "instanceId": "ci_test_user_002",
        "sessions": [
            {
                "sessionKey": "session-financial-analysis",
                "instanceId": "ci_test_user_002",
                "title": "财务分析",
                "workspaceName": "finance-workspace",
                "workspacePath": "D:\Workspaces\finance",
                "totalTokens": 15420,
                "messageCount": 2,
                "sessionCreatedAt": "2026-10-11T12:00:00Z",
                "sessionUpdatedAt": "2026-10-11T12:05:00Z",
                "messages": [
                    {"role": "user", "content": "财报分析需求"},
                    {"role": "assistant", "content": "财报分析结果"},
                ],
            }
        ],
    }

    sync_resp = await async_client.post(
        "/api/client/sessions/sync",
        headers=auth_headers,
        json=sync_payload,
    )
    assert sync_resp.status_code == 200
    assert sync_resp.json()["data"]["syncedCount"] == 1

    admin_tokens = issue_token_pair("admin-user-id", settings)
    admin_headers = {"Authorization": f"Bearer {admin_tokens.access_token}"}

    sessions_resp = await async_client.get("/api/v1/admin/chat-sessions", headers=admin_headers)
    assert sessions_resp.status_code == 200
    sessions = sessions_resp.json()["data"]
    assert len(sessions) == 1
    s = sessions[0]
    assert s["title"] == "财务分析"
    assert s["username"] == "developer"

    detail_resp = await async_client.get(f"/api/v1/admin/chat-sessions/{s['id']}", headers=admin_headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert len(detail["messages"]) == 2
