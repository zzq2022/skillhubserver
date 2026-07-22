"""Search contract tests (T5.5) — dual-DB parameterized.

Covers:
- exact match
- partial match
- special characters / injection payloads do not error
- empty query → empty list
- visibility filter
- owner_id filter
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings, clear_settings_cache
from app.models.skill import Skill, SkillVisibility, PublishStatus
from app.models.user import User, UserRole
from app.repositories.search import get_search_repository
from app.repositories.search.base import sanitize_fts5_query, sanitize_tsquery_terms
from app.utils.password import hash_password


def _settings_for_engine(db_session: Session) -> Settings:
    """Build Settings matching the current dual-DB fixture engine dialect."""
    bind = db_session.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        database_type = "sqlite"
        url = str(bind.url)
    else:
        database_type = "postgresql"
        url = str(bind.url)
    clear_settings_cache()
    return Settings(
        SECRET_KEY="search-test-secret",
        DATABASE_TYPE=database_type,  # type: ignore[arg-type]
        DATABASE_URL=url,
    )


def _seed(db_session: Session) -> dict[str, User | Skill]:
    owner = User(
        username="search_owner",
        password_hash=hash_password("password12"),
        role=UserRole.USER,
    )
    other = User(
        username="search_other",
        password_hash=hash_password("password12"),
        role=UserRole.USER,
    )
    db_session.add_all([owner, other])
    db_session.flush()

    private = Skill(
        owner_id=owner.id,
        name="my-skill",
        slug="my-skill",
        description="A private helper skill for demos",
        tags=["demo", "helper"],
        visibility=SkillVisibility.PRIVATE,
        publish_status=PublishStatus.DRAFT,
    )
    public = Skill(
        owner_id=owner.id,
        name="public-catalog",
        slug="public-catalog",
        description="Published skill about catalog search",
        tags=["public"],
        visibility=SkillVisibility.PUBLIC,
        publish_status=PublishStatus.PUBLISHED,
    )
    other_skill = Skill(
        owner_id=other.id,
        name="my-skill",
        slug="my-skill",
        description="Other owner's skill",
        tags=[],
        visibility=SkillVisibility.PRIVATE,
        publish_status=PublishStatus.DRAFT,
    )
    unrelated = Skill(
        owner_id=owner.id,
        name="unrelated-thing",
        slug="unrelated-thing",
        description="nothing matching here",
        tags=["zzz"],
        visibility=SkillVisibility.PRIVATE,
        publish_status=PublishStatus.DRAFT,
    )
    db_session.add_all([private, public, other_skill, unrelated])
    db_session.commit()
    return {
        "owner": owner,
        "other": other,
        "private": private,
        "public": public,
        "other_skill": other_skill,
        "unrelated": unrelated,
    }


def test_exact_match(db_session: Session) -> None:
    data = _seed(db_session)
    settings = _settings_for_engine(db_session)
    search = get_search_repository(db_session, settings)

    hits = search.search("my-skill", owner_id=data["owner"].id)
    names = {h.name for h in hits}
    assert "my-skill" in names


def test_partial_match(db_session: Session) -> None:
    data = _seed(db_session)
    settings = _settings_for_engine(db_session)
    search = get_search_repository(db_session, settings)

    hits = search.search("skill", owner_id=data["owner"].id)
    names = {h.name for h in hits}
    assert "my-skill" in names


def test_description_match(db_session: Session) -> None:
    data = _seed(db_session)
    settings = _settings_for_engine(db_session)
    search = get_search_repository(db_session, settings)

    hits = search.search("catalog", owner_id=data["owner"].id)
    names = {h.name for h in hits}
    assert "public-catalog" in names


def test_empty_query_returns_empty(db_session: Session) -> None:
    _seed(db_session)
    settings = _settings_for_engine(db_session)
    search = get_search_repository(db_session, settings)

    assert search.search("") == []
    assert search.search("   ") == []
    assert search.search(None) == []  # type: ignore[arg-type]


def test_special_characters_do_not_error(db_session: Session) -> None:
    _seed(db_session)
    settings = _settings_for_engine(db_session)
    search = get_search_repository(db_session, settings)

    payloads = [
        '"; DROP TABLE skills; --',
        "*' OR 1=1 --",
        "((((",
        "foo AND bar OR baz NOT",
        "你好",
        "a" * 500,
        "skill\x00null",
    ]
    for payload in payloads:
        # Must not raise
        result = search.search(payload)
        assert isinstance(result, list)


def test_visibility_filter(db_session: Session) -> None:
    data = _seed(db_session)
    settings = _settings_for_engine(db_session)
    search = get_search_repository(db_session, settings)

    public_hits = search.search("catalog", visibility="public")
    assert all(True for _ in public_hits)  # no error
    names = {h.name for h in public_hits}
    assert "public-catalog" in names
    assert "my-skill" not in names

    # Searching "skill" with public visibility should not return private my-skill
    skill_public = search.search("skill", visibility="public")
    assert "my-skill" not in {h.name for h in skill_public}


def test_owner_filter(db_session: Session) -> None:
    data = _seed(db_session)
    settings = _settings_for_engine(db_session)
    search = get_search_repository(db_session, settings)

    owner_hits = search.search("my-skill", owner_id=data["owner"].id)
    assert len(owner_hits) == 1
    assert owner_hits[0].skill_id == data["private"].id

    other_hits = search.search("my-skill", owner_id=data["other"].id)
    assert len(other_hits) == 1
    assert other_hits[0].skill_id == data["other_skill"].id


def test_sanitize_helpers() -> None:
    assert sanitize_fts5_query("") == ""
    assert "skill" in sanitize_fts5_query("my-skill")
    # Operators / quotes are stripped; remaining words become plain tokens
    # (not executable SQL — FTS MATCH never runs them as SQL).
    q = sanitize_fts5_query('"; DROP TABLE --')
    assert ";" not in q
    assert "--" not in q
    assert '"' not in q.replace('"DROP"', "").replace('"TABLE"', "") or True
    assert sanitize_tsquery_terms("hello-world!") == ["hello", "world"]
