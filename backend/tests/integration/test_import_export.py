"""Import/export ZIP tests (T7.3): happy path, zip-slip, oversized, corrupt, symlink."""

from __future__ import annotations

import io
import stat
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
TEST_SECRET = "test-secret-key-for-import-export"


@pytest.fixture
def ie_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    db_file = tmp_path / "ie.db"
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
async def client(ie_env: Path) -> AsyncIterator[AsyncClient]:
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


def _make_zip(files: dict[str, bytes], *, symlink: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
        if symlink is not None:
            info = zipfile.ZipInfo(symlink)
            # Unix symlink: create_system=3, mode S_IFLNK
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, b"/tmp/evil")
    return buf.getvalue()


GOOD_SKILL_MD = b"""---
name: imported-skill
description: From ZIP
version: 1
tags:
  - demo
---
# Imported Skill

Body content.
"""


@pytest.mark.asyncio
async def test_export_import_roundtrip(client: AsyncClient, ie_env: Path) -> None:
    data = await _login(client)
    created = await client.post(
        "/api/v1/skills",
        json={
            "name": "export-me",
            "description": "to export",
            "content": "# Export Me\n\nHello.\n",
        },
        headers=_csrf(data),
    )
    assert created.status_code == 201, created.text
    skill_id = created.json()["data"]["id"]

    exported = await client.get(f"/api/v1/skills/{skill_id}/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/zip")
    assert exported.content[:2] == b"PK"

    # Delete original so re-import can reuse name
    await client.delete(f"/api/v1/skills/{skill_id}", headers=_csrf(data))

    imported = await client.post(
        "/api/v1/skills/import",
        headers=_csrf(data),
        files={"file": ("export-me.zip", exported.content, "application/zip")},
    )
    assert imported.status_code == 201, imported.text
    skill = imported.json()["data"]
    assert skill["slug"] == "export-me"
    assert skill["visibility"] == "private"
    assert skill["publishStatus"] == "draft"

    content = await client.get(f"/api/v1/skills/{skill['id']}/content")
    assert "Export Me" in content.json()["data"]["content"] or "export" in content.json()[
        "data"
    ]["content"].lower()


@pytest.mark.asyncio
async def test_import_valid_zip(client: AsyncClient) -> None:
    data = await _login(client)
    raw = _make_zip({"SKILL.md": GOOD_SKILL_MD, "assets/helper.txt": b"hi"})
    resp = await client.post(
        "/api/v1/skills/import",
        headers=_csrf(data),
        files={"file": ("pack.zip", raw, "application/zip")},
    )
    assert resp.status_code == 201, resp.text
    skill = resp.json()["data"]
    assert skill["name"] in ("imported-skill", "imported-skill")
    assert skill["description"] == "From ZIP"


@pytest.mark.asyncio
async def test_import_nested_package_folder(client: AsyncClient) -> None:
    data = await _login(client)
    raw = _make_zip({"my-pack/SKILL.md": GOOD_SKILL_MD})
    resp = await client.post(
        "/api/v1/skills/import",
        headers=_csrf(data),
        files={"file": ("nested.zip", raw, "application/zip")},
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_reject_zip_slip(client: AsyncClient) -> None:
    data = await _login(client)
    raw = _make_zip({"../../evil.txt": b"pwned", "SKILL.md": GOOD_SKILL_MD})
    resp = await client.post(
        "/api/v1/skills/import",
        headers=_csrf(data),
        files={"file": ("slip.zip", raw, "application/zip")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "zip_slip"


@pytest.mark.asyncio
async def test_reject_absolute_path(client: AsyncClient) -> None:
    data = await _login(client)
    raw = _make_zip({"/tmp/evil.txt": b"nope", "SKILL.md": GOOD_SKILL_MD})
    resp = await client.post(
        "/api/v1/skills/import",
        headers=_csrf(data),
        files={"file": ("abs.zip", raw, "application/zip")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "zip_slip"


@pytest.mark.asyncio
async def test_reject_symlink(client: AsyncClient) -> None:
    data = await _login(client)
    raw = _make_zip(
        {"SKILL.md": GOOD_SKILL_MD},
        symlink="link-to-etc",
    )
    resp = await client.post(
        "/api/v1/skills/import",
        headers=_csrf(data),
        files={"file": ("symlink.zip", raw, "application/zip")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "zip_symlink"


@pytest.mark.asyncio
async def test_reject_corrupt_zip(client: AsyncClient) -> None:
    data = await _login(client)
    resp = await client.post(
        "/api/v1/skills/import",
        headers=_csrf(data),
        files={"file": ("bad.zip", b"not-a-zip-at-all", "application/zip")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_zip"


@pytest.mark.asyncio
async def test_reject_missing_skill_md(client: AsyncClient) -> None:
    data = await _login(client)
    raw = _make_zip({"readme.txt": b"no skill"})
    resp = await client.post(
        "/api/v1/skills/import",
        headers=_csrf(data),
        files={"file": ("noskill.zip", raw, "application/zip")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "missing_skill_md"


@pytest.mark.asyncio
async def test_reject_oversized_zip(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    data = await _login(client)
    # Force tiny limit on service defaults via monkeypatch of module constant path
    import app.services.import_export_service as ies

    monkeypatch.setattr(ies, "DEFAULT_MAX_ZIP_BYTES", 100)

    raw = _make_zip({"SKILL.md": GOOD_SKILL_MD + b"x" * 200})
    # Compressed may still be small; ensure raw length > 100 by padding zip
    if len(raw) <= 100:
        raw = raw + b"\x00" * (101 - len(raw))
        # That corrupts zip; use larger content instead
        raw = _make_zip({"SKILL.md": b"y" * 5000})

    # Patch the service class limit by injecting small max via settings isn't available;
    # patch ImportExportService.__init__ max after construction by monkeypatching attr used in import
    original_init = ies.ImportExportService.__init__

    def _tiny_init(self, session, settings=None, workspace=None):  # noqa: ANN001
        original_init(self, session, settings, workspace)
        self._max_zip = 50

    monkeypatch.setattr(ies.ImportExportService, "__init__", _tiny_init)

    resp = await client.post(
        "/api/v1/skills/import",
        headers=_csrf(data),
        files={"file": ("big.zip", raw, "application/zip")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "zip_too_large"
