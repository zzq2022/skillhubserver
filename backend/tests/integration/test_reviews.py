"""Review workflow + public hub integration tests (T6.6).

Covers: submit → approve → public hub / submit → reject → private /
unpublish / re-submit after reject.
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
TEST_SECRET = "test-secret-key-for-reviews-integration"


@pytest.fixture
def reviews_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    db_file = tmp_path / "reviews.db"
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
async def client(reviews_env: Path) -> AsyncIterator[AsyncClient]:
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


async def _bootstrap(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/bootstrap/init",
        json={"username": "admin", "password": "adminpass1"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _csrf(data: dict) -> dict[str, str]:
    return {"X-CSRF-Token": data["csrfToken"]}


async def _create_skill(client: AsyncClient, data: dict, name: str = "pub-skill") -> dict:
    resp = await client.post(
        "/api/v1/skills",
        json={
            "name": name,
            "description": f"Description for {name}",
            "tags": ["hub"],
            "content": f"# {name}\n\nBody.\n",
        },
        headers=_csrf(data),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_submit_approve_appears_on_hub(client: AsyncClient) -> None:
    data = await _bootstrap(client)
    skill = await _create_skill(client, data, "hub-skill")
    skill_id = skill["id"]

    # Draft skill not on public hub
    hub = await client.get("/api/v1/hub/skills")
    assert hub.status_code == 200
    assert hub.json()["pagination"]["total"] == 0

    submit = await client.post(
        f"/api/v1/skills/{skill_id}/submit",
        headers=_csrf(data),
    )
    assert submit.status_code == 200, submit.text
    review = submit.json()["data"]
    assert review["status"] == "pending"
    assert review["skillId"] == skill_id

    got = await client.get(f"/api/v1/skills/{skill_id}")
    assert got.json()["data"]["publishStatus"] == "pending_review"
    assert got.json()["data"]["visibility"] == "private"

    # Still not public
    hub = await client.get("/api/v1/hub/skills")
    assert hub.json()["pagination"]["total"] == 0

    pending = await client.get("/api/v1/admin/reviews")
    assert pending.status_code == 200
    assert pending.json()["pagination"]["total"] == 1
    assert pending.json()["data"][0]["id"] == review["id"]

    approved = await client.post(
        f"/api/v1/admin/reviews/{review['id']}/approve",
        headers=_csrf(data),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"

    got = await client.get(f"/api/v1/skills/{skill_id}")
    assert got.json()["data"]["publishStatus"] == "published"
    assert got.json()["data"]["visibility"] == "public"

    hub = await client.get("/api/v1/hub/skills")
    assert hub.status_code == 200
    assert hub.json()["pagination"]["total"] == 1
    item = hub.json()["data"][0]
    assert item["slug"] == "hub-skill"
    assert item["owner"] == "admin"

    detail = await client.get("/api/v1/hub/skills/admin/hub-skill")
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == skill_id

    download = await client.get("/api/v1/hub/skills/admin/hub-skill/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/zip")
    assert download.content[:2] == b"PK"


@pytest.mark.asyncio
async def test_submit_reject_stays_private(client: AsyncClient) -> None:
    data = await _bootstrap(client)
    skill = await _create_skill(client, data, "reject-me")
    skill_id = skill["id"]

    submit = await client.post(
        f"/api/v1/skills/{skill_id}/submit",
        headers=_csrf(data),
    )
    review_id = submit.json()["data"]["id"]

    rejected = await client.post(
        f"/api/v1/admin/reviews/{review_id}/reject",
        json={"comment": "Needs more docs"},
        headers=_csrf(data),
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["status"] == "rejected"
    assert rejected.json()["data"]["comment"] == "Needs more docs"

    got = await client.get(f"/api/v1/skills/{skill_id}")
    assert got.json()["data"]["publishStatus"] == "rejected"
    assert got.json()["data"]["visibility"] == "private"

    hub = await client.get("/api/v1/hub/skills")
    assert hub.json()["pagination"]["total"] == 0

    missing = await client.get("/api/v1/hub/skills/admin/reject-me")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_unpublish_and_resubmit(client: AsyncClient) -> None:
    data = await _bootstrap(client)
    skill = await _create_skill(client, data, "toggle-skill")
    skill_id = skill["id"]

    submit = await client.post(
        f"/api/v1/skills/{skill_id}/submit",
        headers=_csrf(data),
    )
    review_id = submit.json()["data"]["id"]
    await client.post(
        f"/api/v1/admin/reviews/{review_id}/approve",
        headers=_csrf(data),
    )

    hub = await client.get("/api/v1/hub/skills")
    assert hub.json()["pagination"]["total"] == 1

    unpub = await client.post(
        f"/api/v1/admin/skills/{skill_id}/unpublish",
        headers=_csrf(data),
    )
    assert unpub.status_code == 200, unpub.text
    assert unpub.json()["data"]["visibility"] == "private"
    assert unpub.json()["data"]["publishStatus"] == "draft"
    assert unpub.json()["data"]["isPublic"] is False

    hub = await client.get("/api/v1/hub/skills")
    assert hub.json()["pagination"]["total"] == 0

    # Re-submit after unpublish (draft)
    submit2 = await client.post(
        f"/api/v1/skills/{skill_id}/submit",
        headers=_csrf(data),
    )
    assert submit2.status_code == 200, submit2.text
    review2 = submit2.json()["data"]
    assert review2["status"] == "pending"
    assert review2["id"] != review_id

    got = await client.get(f"/api/v1/skills/{skill_id}")
    assert got.json()["data"]["publishStatus"] == "pending_review"


@pytest.mark.asyncio
async def test_admin_list_and_force_publish(client: AsyncClient) -> None:
    """Admin skill management: list all + force 上架 without review."""
    data = await _bootstrap(client)
    published = await _create_skill(client, data, "listed-pub")
    draft = await _create_skill(client, data, "listed-draft")

    submit = await client.post(
        f"/api/v1/skills/{published['id']}/submit",
        headers=_csrf(data),
    )
    await client.post(
        f"/api/v1/admin/reviews/{submit.json()['data']['id']}/approve",
        headers=_csrf(data),
    )

    all_skills = await client.get("/api/v1/admin/skills")
    assert all_skills.status_code == 200
    assert all_skills.json()["pagination"]["total"] == 2
    by_id = {s["id"]: s for s in all_skills.json()["data"]}
    assert by_id[published["id"]]["isPublic"] is True
    assert by_id[draft["id"]]["isPublic"] is False
    assert by_id[draft["id"]]["publishStatus"] == "draft"

    only_public = await client.get("/api/v1/admin/skills?status=public")
    assert only_public.json()["pagination"]["total"] == 1
    assert only_public.json()["data"][0]["id"] == published["id"]

    force = await client.post(
        f"/api/v1/admin/skills/{draft['id']}/publish",
        headers=_csrf(data),
    )
    assert force.status_code == 200, force.text
    assert force.json()["data"]["isPublic"] is True
    assert force.json()["data"]["visibility"] == "public"
    assert force.json()["data"]["publishStatus"] == "published"

    hub = await client.get("/api/v1/hub/skills")
    assert hub.json()["pagination"]["total"] == 2

    # Unpublish then force-publish again
    unpub = await client.post(
        f"/api/v1/admin/skills/{draft['id']}/unpublish",
        headers=_csrf(data),
    )
    assert unpub.json()["data"]["isPublic"] is False
    hub = await client.get("/api/v1/hub/skills")
    assert hub.json()["pagination"]["total"] == 1

    again = await client.post(
        f"/api/v1/admin/skills/{draft['id']}/publish",
        headers=_csrf(data),
    )
    assert again.status_code == 200
    assert again.json()["data"]["isPublic"] is True
    hub = await client.get("/api/v1/hub/skills")
    assert hub.json()["pagination"]["total"] == 2


@pytest.mark.asyncio
async def test_reject_then_resubmit(client: AsyncClient) -> None:
    data = await _bootstrap(client)
    skill = await _create_skill(client, data, "retry-skill")
    skill_id = skill["id"]

    submit = await client.post(
        f"/api/v1/skills/{skill_id}/submit",
        headers=_csrf(data),
    )
    review_id = submit.json()["data"]["id"]
    await client.post(
        f"/api/v1/admin/reviews/{review_id}/reject",
        json={"comment": "fix"},
        headers=_csrf(data),
    )

    submit2 = await client.post(
        f"/api/v1/skills/{skill_id}/submit",
        headers=_csrf(data),
    )
    assert submit2.status_code == 200, submit2.text
    assert submit2.json()["data"]["status"] == "pending"
    assert submit2.json()["data"]["id"] != review_id

    got = await client.get(f"/api/v1/skills/{skill_id}")
    assert got.json()["data"]["publishStatus"] == "pending_review"


@pytest.mark.asyncio
async def test_cannot_submit_when_published(client: AsyncClient) -> None:
    data = await _bootstrap(client)
    skill = await _create_skill(client, data, "already-pub")
    skill_id = skill["id"]

    submit = await client.post(
        f"/api/v1/skills/{skill_id}/submit",
        headers=_csrf(data),
    )
    review_id = submit.json()["data"]["id"]
    await client.post(
        f"/api/v1/admin/reviews/{review_id}/approve",
        headers=_csrf(data),
    )

    again = await client.post(
        f"/api/v1/skills/{skill_id}/submit",
        headers=_csrf(data),
    )
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "invalid_review_state"


@pytest.mark.asyncio
async def test_idempotent_submit_while_pending(client: AsyncClient) -> None:
    data = await _bootstrap(client)
    skill = await _create_skill(client, data, "pending-once")
    skill_id = skill["id"]

    first = await client.post(
        f"/api/v1/skills/{skill_id}/submit",
        headers=_csrf(data),
    )
    second = await client.post(
        f"/api/v1/skills/{skill_id}/submit",
        headers=_csrf(data),
    )
    assert second.status_code == 200
    assert second.json()["data"]["id"] == first.json()["data"]["id"]


@pytest.mark.asyncio
async def test_non_owner_cannot_submit(client: AsyncClient) -> None:
    data = await _bootstrap(client)
    # Create regular user
    await client.post(
        "/api/v1/admin/users",
        json={"username": "alice", "password": "alicepass1", "role": "user"},
        headers=_csrf(data),
    )
    skill = await _create_skill(client, data, "admin-only")
    skill_id = skill["id"]

    await client.post("/api/v1/auth/logout", headers=_csrf(data))
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "alicepass1"},
    )
    assert login.status_code == 200
    alice = login.json()["data"]

    forbidden = await client.post(
        f"/api/v1/skills/{skill_id}/submit",
        headers=_csrf(alice),
    )
    assert forbidden.status_code == 403
