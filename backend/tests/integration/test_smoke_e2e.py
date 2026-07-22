"""API-level smoke path (T10.5 subset without Docker).

bootstrap → login → create skill → search → export
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import clear_settings_cache
from app.database import get_db, reset_engine, to_async_url
from app.main import app

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
TEST_SECRET = "test-secret-key-for-smoke-e2e"


@pytest.fixture
def smoke_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    db_file = tmp_path / "smoke.db"
    data_root = tmp_path / "data"
    data_root.mkdir()
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_TYPE", "sqlite")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("DATA_ROOT", str(data_root))
    clear_settings_cache()
    reset_engine()

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")
    yield data_root
    reset_engine()
    clear_settings_cache()


@pytest.fixture
async def client(smoke_env: Path) -> AsyncIterator[AsyncClient]:
    from app.config import get_settings

    settings = get_settings()
    async_url = to_async_url(settings.DATABASE_URL, "sqlite")
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


@pytest.mark.asyncio
async def test_smoke_bootstrap_skill_search_export(client: AsyncClient) -> None:
    # Health
    health = await client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["data"]["status"] == "ok"
    assert health.headers.get("X-Content-Type-Options") == "nosniff"

    # Bootstrap
    boot = await client.get("/api/v1/bootstrap")
    assert boot.status_code == 200
    assert boot.json()["data"]["initialized"] is False

    init = await client.post(
        "/api/v1/bootstrap/init",
        json={"username": "admin", "password": "adminpass1"},
    )
    assert init.status_code == 200
    csrf = init.json()["data"]["csrfToken"]
    headers = {"X-CSRF-Token": csrf}

    # Create skill
    created = await client.post(
        "/api/v1/skills",
        json={
            "name": "smoke-skill",
            "description": "smoke test searchable skill",
            "tags": ["smoke"],
            "content": "# Smoke\n\nHello smoke world.\n",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    skill_id = created.json()["data"]["id"]

    # Search
    search = await client.get("/api/v1/skills", params={"q": "smoke"})
    assert search.status_code == 200
    ids = [s["id"] for s in search.json()["data"]]
    assert skill_id in ids

    # Export
    exported = await client.get(f"/api/v1/skills/{skill_id}/export")
    assert exported.status_code == 200
    assert exported.content[:2] == b"PK"

    # Re-login path
    await client.post("/api/v1/auth/logout", headers=headers)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "adminpass1"},
    )
    assert login.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "admin"
    assert me.json()["data"].get("csrfToken")
