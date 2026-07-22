"""Skill CRUD + version integration tests (T4.6)."""

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
TEST_SECRET = "test-secret-key-for-skills-integration"


@pytest.fixture
def skills_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    db_file = tmp_path / "skills.db"
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
async def client(skills_env: Path) -> AsyncIterator[AsyncClient]:
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


async def _login(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/bootstrap/init",
        json={"username": "admin", "password": "adminpass1"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _csrf(data: dict) -> dict[str, str]:
    return {"X-CSRF-Token": data["csrfToken"]}


@pytest.mark.asyncio
async def test_create_get_list_delete_skill(
    client: AsyncClient, skills_env: Path
) -> None:
    data = await _login(client)

    created = await client.post(
        "/api/v1/skills",
        json={
            "name": "my-skill",
            "description": "A test skill",
            "tags": ["demo"],
            "content": "# Hello\n\nBody here.\n",
        },
        headers=_csrf(data),
    )
    assert created.status_code == 201, created.text
    skill = created.json()["data"]
    assert skill["name"] == "my-skill"
    assert skill["slug"] == "my-skill"
    assert skill["visibility"] == "private"
    assert skill["publishStatus"] == "draft"
    skill_id = skill["id"]

    # Workspace files exist
    pkg_dirs = list((skills_env / "skills").glob(f"my-skill__{skill_id}"))
    assert len(pkg_dirs) == 1
    assert (pkg_dirs[0] / "SKILL.md").is_file()

    got = await client.get(f"/api/v1/skills/{skill_id}")
    assert got.status_code == 200
    assert got.json()["data"]["id"] == skill_id

    listed = await client.get("/api/v1/skills")
    assert listed.status_code == 200
    assert listed.json()["pagination"]["total"] == 1
    assert listed.json()["data"][0]["id"] == skill_id

    deleted = await client.delete(
        f"/api/v1/skills/{skill_id}",
        headers=_csrf(data),
    )
    assert deleted.status_code == 200
    assert not pkg_dirs[0].exists()

    missing = await client.get(f"/api/v1/skills/{skill_id}")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_update_metadata_and_content(client: AsyncClient) -> None:
    data = await _login(client)
    created = await client.post(
        "/api/v1/skills",
        json={"name": "edit-me", "description": "old"},
        headers=_csrf(data),
    )
    skill_id = created.json()["data"]["id"]

    updated = await client.put(
        f"/api/v1/skills/{skill_id}",
        json={"description": "new desc", "tags": ["a", "b"]},
        headers=_csrf(data),
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["description"] == "new desc"
    assert updated.json()["data"]["tags"] == ["a", "b"]

    content_resp = await client.get(f"/api/v1/skills/{skill_id}/content")
    assert content_resp.status_code == 200
    assert "edit-me" in content_resp.json()["data"]["content"]

    new_md = "---\nname: edit-me\ndescription: from-md\nversion: 1\ntags:\n- x\n---\n# Updated\n"
    put_content = await client.put(
        f"/api/v1/skills/{skill_id}/content",
        json={"content": new_md},
        headers=_csrf(data),
    )
    assert put_content.status_code == 200
    assert "Updated" in put_content.json()["data"]["content"]


@pytest.mark.asyncio
async def test_unique_per_user_and_version_snapshot(
    client: AsyncClient, skills_env: Path
) -> None:
    data = await _login(client)

    r1 = await client.post(
        "/api/v1/skills",
        json={"name": "dup-skill"},
        headers=_csrf(data),
    )
    assert r1.status_code == 201
    skill_id = r1.json()["data"]["id"]

    r2 = await client.post(
        "/api/v1/skills",
        json={"name": "dup-skill"},
        headers=_csrf(data),
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "skill_name_conflict"

    v1 = await client.post(
        f"/api/v1/skills/{skill_id}/versions",
        json={"notes": "first snapshot"},
        headers=_csrf(data),
    )
    assert v1.status_code == 201, v1.text
    assert v1.json()["data"]["versionNumber"] == 1
    assert "versions/0001/SKILL.md" in v1.json()["data"]["snapshotPath"]

    # Snapshot file on disk
    snap = skills_env / "skills" / f"dup-skill__{skill_id}" / "versions" / "0001" / "SKILL.md"
    assert snap.is_file()

    versions = await client.get(f"/api/v1/skills/{skill_id}/versions")
    assert versions.status_code == 200
    assert len(versions.json()["data"]) == 1


@pytest.mark.asyncio
async def test_csrf_required_on_create(client: AsyncClient) -> None:
    await _login(client)
    resp = await client.post(
        "/api/v1/skills",
        json={"name": "no-csrf"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "csrf_failed"
