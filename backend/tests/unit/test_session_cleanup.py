"""Session cleanup unit test (T10.3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import clear_settings_cache
from app.database import reset_engine, to_sync_url
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole
from app.repositories.session_repo import SessionRepository
from app.utils.password import hash_password

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"


@pytest.fixture
def db_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    db_file = tmp_path / "cleanup.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_TYPE", "sqlite")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SECRET_KEY", "cleanup-test-secret")
    clear_settings_cache()
    reset_engine()
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")
    yield url
    reset_engine()
    clear_settings_cache()


def test_cleanup_expired_sessions(db_url: str) -> None:
    engine = create_engine(to_sync_url(db_url, "sqlite"))

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        user = User(
            username="u1",
            password_hash=hash_password("password1"),
            role=UserRole.USER,
        )
        session.add(user)
        session.flush()

        now = datetime.now(timezone.utc)
        expired = SessionModel(
            id="expired-session-id-0001",
            user_id=user.id,
            csrf_token="csrf1",
            expires_at=now - timedelta(hours=1),
            last_active_at=now - timedelta(hours=2),
        )
        active = SessionModel(
            id="active-session-id-0001",
            user_id=user.id,
            csrf_token="csrf2",
            expires_at=now + timedelta(days=1),
            last_active_at=now,
        )
        session.add_all([expired, active])
        session.commit()

        repo = SessionRepository(session)
        removed = repo.cleanup_expired()
        session.commit()
        assert removed == 1
        assert session.get(SessionModel, "expired-session-id-0001") is None
        assert session.get(SessionModel, "active-session-id-0001") is not None
