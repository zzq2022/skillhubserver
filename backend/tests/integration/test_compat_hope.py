"""Hope / AgentWork compatibility layer: /api/auth + /api/skillhub."""

from __future__ import annotations

import base64
import io
import zipfile
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
TEST_SECRET = "test-secret-key-for-hope-compat-32bytes!"


@pytest.fixture
def compat_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    db_file = tmp_path / "compat.db"
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
async def client(compat_env: Path) -> AsyncIterator[AsyncClient]:
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


async def _bootstrap(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/bootstrap/init",
        json={"username": "hopeuser", "password": "hopepass1"},
    )
    assert resp.status_code == 200, resp.text


async def _token_login(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/auth/login",
        json={"username": "hopeuser", "password": "hopepass1"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "accessToken" in data
    assert "refreshToken" in data
    assert data["user"]["username"] == "hopeuser"
    return data


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _skill_zip(name: str = "hope-skill") -> bytes:
    content = f"""---
name: {name}
description: Hope package
version: 1
tags:
  - hope
---
# {name}

Body from Hope.
""".encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", content)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_compat_login_and_refresh(client: AsyncClient) -> None:
    await _bootstrap(client)
    tokens = await _token_login(client)

    # Wrong password
    bad = await client.post(
        "/api/auth/login",
        json={"username": "hopeuser", "password": "wrong"},
    )
    assert bad.status_code == 401

    # Refresh
    ref = await client.post(
        "/api/auth/refresh",
        json={"refreshToken": tokens["refreshToken"]},
    )
    assert ref.status_code == 200, ref.text
    new = ref.json()["data"]
    assert new["accessToken"]
    assert new["user"]["username"] == "hopeuser"

    # Bad refresh
    bad_ref = await client.post(
        "/api/auth/refresh",
        json={"refreshToken": "garbage"},
    )
    assert bad_ref.status_code == 401


@pytest.mark.asyncio
async def test_review_submission_and_private_list(client: AsyncClient) -> None:
    await _bootstrap(client)
    tokens = await _token_login(client)
    headers = _bearer(tokens["accessToken"])

    raw = _skill_zip("hope-demo")
    body = {
        "fileName": "hope-demo.zip",
        "packageBase64": base64.b64encode(raw).decode("ascii"),
        "name": "hope-demo",
        "description": "Submitted from Hope",
        "category": "dev",
        "tags": ["hope", "demo"],
    }
    resp = await client.post(
        "/api/skillhub/review-submissions",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["approvalStatus"] == "pending"
    assert data["visibility"] == "private"
    assert data["registrySlug"].endswith("/hope-demo") or "hope-demo" in data["slug"]
    skill_id = data["skillId"]

    priv = await client.get("/api/skillhub/private", headers=headers)
    assert priv.status_code == 200, priv.text
    items = priv.json()["data"]
    assert any(i["id"] == skill_id for i in items)
    match = next(i for i in items if i["id"] == skill_id)
    assert match["approvalStatus"] == "pending"

    detail = await client.get(f"/api/skillhub/private/{skill_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["approvalStatus"] == "pending"


@pytest.mark.asyncio
async def test_public_catalog_stats_and_download(client: AsyncClient) -> None:
    await _bootstrap(client)
    tokens = await _token_login(client)
    headers = _bearer(tokens["accessToken"])

    # Submit then approve via admin session path
    raw = _skill_zip("public-skill")
    sub = await client.post(
        "/api/skillhub/review-submissions",
        json={
            "fileName": "public-skill.zip",
            "packageBase64": base64.b64encode(raw).decode("ascii"),
            "name": "public-skill",
            "category": "ai",
        },
        headers=headers,
    )
    assert sub.status_code == 200, sub.text
    skill_id = sub.json()["data"]["skillId"]
    review_id = sub.json()["data"]["reviewId"]

    # Browser login for admin approve (bootstrap user is admin)
    session_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "hopeuser", "password": "hopepass1"},
    )
    assert session_login.status_code == 200, session_login.text
    csrf = session_login.json()["data"]["csrfToken"]

    approve = await client.post(
        f"/api/v1/admin/reviews/{review_id}/approve",
        headers={"X-CSRF-Token": csrf},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["data"]["status"] == "approved"

    # Mark featured via DB for featured endpoint
    from app.database import get_async_session_factory
    from app.models.skill import Skill

    factory = get_async_session_factory()
    async with factory() as session:
        skill = await session.get(Skill, skill_id)
        assert skill is not None
        skill.featured = True
        await session.commit()

    # Public browse (no auth)
    pub = await client.get("/api/skillhub/public")
    assert pub.status_code == 200, pub.text
    page = pub.json()["data"]
    assert page["total"] >= 1
    assert any(i["id"] == skill_id for i in page["items"])
    # Hope serde uses aliases (registrySlug←slug, downloads←downloadCount, …).
    # Sending both primary and alias keys makes client decode fail → empty list.
    sample = next(i for i in page["items"] if i["id"] == skill_id)
    for forbidden in ("downloads", "stars", "views", "authorUsername"):
        assert forbidden not in sample, f"duplicate Hope field {forbidden}"
    assert "registrySlug" in sample
    assert "downloadCount" in sample
    assert "starCount" in sample
    assert "slug" not in sample

    stats = await client.get("/api/skillhub/public/stats")
    assert stats.status_code == 200
    s = stats.json()["data"]
    assert s["totalSkills"] >= 1

    featured = await client.get("/api/skillhub/public/featured")
    assert featured.status_code == 200
    assert any(i["id"] == skill_id for i in featured.json()["data"])

    detail = await client.get(f"/api/skillhub/public/{skill_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["name"]

    # Star + view
    star = await client.post(
        f"/api/skillhub/public/{skill_id}/star",
        headers=headers,
    )
    assert star.status_code == 200, star.text
    assert star.json()["data"]["starred"] is True

    view = await client.post(f"/api/skillhub/public/{skill_id}/view")
    assert view.status_code == 200

    # Download
    dl = await client.get(f"/api/skillhub/{skill_id}/download")
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith("application/zip")
    assert len(dl.content) > 20

    # Private list shows shared/approved
    priv = await client.get("/api/skillhub/private", headers=headers)
    match = next(i for i in priv.json()["data"] if i["id"] == skill_id)
    assert match["visibility"] == "shared"
    assert match["approvalStatus"] == "approved"


@pytest.mark.asyncio
async def test_private_requires_auth(client: AsyncClient) -> None:
    await _bootstrap(client)
    # Bootstrap sets a session cookie; dual auth accepts it. Clear cookies to
    # assert unauthenticated access is rejected.
    client.cookies.clear()
    resp = await client.get("/api/skillhub/private")
    assert resp.status_code == 401
