"""Media upload tests (T8.4): happy path, type reject, size limit, path-traversal name."""

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
TEST_SECRET = "test-secret-key-for-media"

# Minimal valid 1x1 PNG
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def media_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    db_file = tmp_path / "media.db"
    data_root = tmp_path / "data"
    data_root.mkdir()
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_TYPE", "sqlite")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("DATA_ROOT", str(data_root))
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "1024")  # 1 KB for size tests
    clear_settings_cache()
    reset_engine()

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")
    yield data_root
    reset_engine()
    clear_settings_cache()


@pytest.fixture
async def client(media_env: Path) -> AsyncIterator[AsyncClient]:
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
async def test_upload_get_delete(client: AsyncClient, media_env: Path) -> None:
    data = await _login(client)
    uploaded = await client.post(
        "/api/v1/media/upload",
        headers=_csrf(data),
        files={"file": ("photo.png", PNG_1X1, "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    media = uploaded.json()["data"]
    assert media["contentType"] == "image/png"
    assert media["sizeBytes"] == len(PNG_1X1)
    assert media["filename"].endswith(".png")
    media_id = media["id"]

    # File on disk under DATA_ROOT/media/YYYY/MM/
    files = list((media_env / "media").rglob("*.png"))
    assert len(files) == 1

    got = await client.get(f"/api/v1/media/{media_id}")
    assert got.status_code == 200
    assert got.content == PNG_1X1
    assert got.headers["content-type"].startswith("image/png")

    deleted = await client.delete(
        f"/api/v1/media/{media_id}",
        headers=_csrf(data),
    )
    assert deleted.status_code == 200
    assert not files[0].exists()

    missing = await client.get(f"/api/v1/media/{media_id}")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_reject_unsupported_type(client: AsyncClient) -> None:
    data = await _login(client)
    resp = await client.post(
        "/api/v1/media/upload",
        headers=_csrf(data),
        files={"file": ("evil.exe", b"MZ....", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_media_type"


@pytest.mark.asyncio
async def test_reject_oversized(client: AsyncClient) -> None:
    data = await _login(client)
    big = b"x" * 2000  # > MAX_UPLOAD_SIZE=1024
    resp = await client.post(
        "/api/v1/media/upload",
        headers=_csrf(data),
        files={"file": ("big.png", big, "image/png")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "file_too_large"


@pytest.mark.asyncio
async def test_sanitize_path_traversal_filename(
    client: AsyncClient, media_env: Path
) -> None:
    data = await _login(client)
    evil_name = "../../etc/passwd.png"
    resp = await client.post(
        "/api/v1/media/upload",
        headers=_csrf(data),
        files={"file": (evil_name, PNG_1X1, "image/png")},
    )
    assert resp.status_code == 201, resp.text
    media = resp.json()["data"]
    # Display name is basename only, no path segments
    assert ".." not in media["filename"]
    assert "/" not in media["filename"]
    assert "\\" not in media["filename"]

    # Nothing written outside media root
    outside = media_env.parent / "etc"
    assert not outside.exists()
    files = list((media_env / "media").rglob("*"))
    assert any(f.is_file() for f in files)
    for f in files:
        if f.is_file():
            assert "media" in f.parts


@pytest.mark.asyncio
async def test_require_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/media/upload",
        files={"file": ("a.png", PNG_1X1, "image/png")},
    )
    # CSRF or auth failure
    assert resp.status_code in (401, 403)
