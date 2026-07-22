"""Verify Alembic migrations on SQLite and (when available) PostgreSQL.

Covers T1.5: migrations execute on both backends and produce the expected
schema (tables, unique constraints, foreign keys).
"""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from app.models import (
    Media,
    PublishStatus,
    Review,
    ReviewStatus,
    Session as SessionModel,
    Skill,
    SkillVersion,
    SkillVisibility,
    User,
    UserRole,
)
from tests.conftest import EXPECTED_TABLES


def test_migration_creates_all_tables(db_engine: Engine) -> None:
    """upgrade head must create every application table plus alembic_version."""
    inspector = inspect(db_engine)
    tables = set(inspector.get_table_names())
    missing = EXPECTED_TABLES - tables
    assert not missing, f"Missing tables after migration: {sorted(missing)}"


def test_users_unique_username(db_session: Session) -> None:
    """users.username is unique."""
    u1 = User(username="alice", password_hash="x", role=UserRole.ADMIN)
    db_session.add(u1)
    db_session.commit()

    u2 = User(username="alice", password_hash="y", role=UserRole.USER)
    db_session.add(u2)
    try:
        db_session.commit()
        raised = False
    except Exception:
        db_session.rollback()
        raised = True
    assert raised, "Duplicate username should violate unique constraint"


def test_skills_unique_owner_slug(db_session: Session) -> None:
    """UNIQUE(owner_id, slug) — same slug under one owner is rejected."""
    owner = User(username="owner1", password_hash="x", role=UserRole.USER)
    db_session.add(owner)
    db_session.flush()

    s1 = Skill(
        owner_id=owner.id,
        name="My Skill",
        slug="my-skill",
        tags=[],
        visibility=SkillVisibility.PRIVATE,
        publish_status=PublishStatus.DRAFT,
    )
    db_session.add(s1)
    db_session.commit()

    s2 = Skill(
        owner_id=owner.id,
        name="My Skill 2",
        slug="my-skill",
        tags=[],
    )
    db_session.add(s2)
    try:
        db_session.commit()
        raised = False
    except Exception:
        db_session.rollback()
        raised = True
    assert raised, "Duplicate (owner_id, slug) should violate unique constraint"


def test_skills_same_slug_different_owners(db_session: Session) -> None:
    """Different owners may share the same skill slug (per-user uniqueness)."""
    a = User(username="user_a", password_hash="x", role=UserRole.USER)
    b = User(username="user_b", password_hash="x", role=UserRole.USER)
    db_session.add_all([a, b])
    db_session.flush()

    db_session.add_all(
        [
            Skill(owner_id=a.id, name="S", slug="shared-slug", tags=[]),
            Skill(owner_id=b.id, name="S", slug="shared-slug", tags=[]),
        ]
    )
    db_session.commit()

    count = db_session.query(Skill).filter(Skill.slug == "shared-slug").count()
    assert count == 2


def test_cascade_delete_user_removes_skills_and_sessions(db_session: Session) -> None:
    """ON DELETE CASCADE from users drops owned skills and sessions."""
    from datetime import datetime, timedelta, timezone

    user = User(username="cascade_user", password_hash="x", role=UserRole.USER)
    db_session.add(user)
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        SessionModel(
            id="sess_" + "a" * 59,
            user_id=user.id,
            csrf_token="c" * 64,
            expires_at=now + timedelta(days=1),
            last_active_at=now,
        )
    )
    skill = Skill(owner_id=user.id, name="Gone", slug="gone", tags=[])
    db_session.add(skill)
    db_session.flush()
    db_session.add(
        SkillVersion(
            skill_id=skill.id,
            version_number=1,
            snapshot_path="versions/0001/SKILL.md",
        )
    )
    db_session.add(
        Media(
            owner_id=user.id,
            filename="a.png",
            content_type="image/png",
            size_bytes=10,
            storage_path="media/2026/07/a.png",
        )
    )
    db_session.commit()

    user_id = user.id
    db_session.delete(user)
    db_session.commit()

    assert db_session.get(User, user_id) is None
    assert db_session.query(Skill).filter(Skill.owner_id == user_id).count() == 0
    assert db_session.query(SessionModel).filter(SessionModel.user_id == user_id).count() == 0
    assert db_session.query(Media).filter(Media.owner_id == user_id).count() == 0


def test_review_and_enum_values(db_session: Session) -> None:
    """Enum columns accept the documented string values."""
    admin = User(username="rev_admin", password_hash="x", role=UserRole.ADMIN)
    author = User(username="rev_author", password_hash="x", role=UserRole.USER)
    db_session.add_all([admin, author])
    db_session.flush()

    skill = Skill(
        owner_id=author.id,
        name="Review Me",
        slug="review-me",
        tags=["demo"],
        visibility=SkillVisibility.PRIVATE,
        publish_status=PublishStatus.PENDING_REVIEW,
    )
    db_session.add(skill)
    db_session.flush()

    review = Review(
        skill_id=skill.id,
        submitter_id=author.id,
        status=ReviewStatus.PENDING,
    )
    db_session.add(review)
    db_session.commit()

    loaded = db_session.get(Review, review.id)
    assert loaded is not None
    assert loaded.status == ReviewStatus.PENDING
    assert loaded.skill.publish_status == PublishStatus.PENDING_REVIEW


def test_foreign_keys_enabled(db_engine: Engine) -> None:
    """SQLite foreign_keys PRAGMA is ON; orphan inserts fail on both backends."""
    with db_engine.connect() as conn:
        dialect = db_engine.dialect.name
        if dialect == "sqlite":
            row = conn.execute(text("PRAGMA foreign_keys")).fetchone()
            assert row is not None and int(row[0]) == 1

        # Attempt insert into sessions with a non-existent user_id
        try:
            conn.execute(
                text(
                    "INSERT INTO sessions (id, user_id, csrf_token, expires_at, last_active_at) "
                    "VALUES ('orphan_session_id_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', "
                    "'00000000-0000-0000-0000-000000000000', "
                    "'csrf_token_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            conn.commit()
            raised = False
        except Exception:
            conn.rollback()
            raised = True
        assert raised, "Insert with missing user_id FK should fail"
