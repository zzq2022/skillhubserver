"""Full-text search adapters.

Factory selects SQLite FTS5 or PostgreSQL tsvector based on DATABASE_TYPE.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.repositories.search.base import SearchRepository, SkillSearchResult
from app.repositories.search.pg_tsvector import PgTsvectorSearchRepository
from app.repositories.search.sqlite_fts import SqliteFtsSearchRepository

__all__ = [
    "SearchRepository",
    "SkillSearchResult",
    "get_search_repository",
]


def get_search_repository(
    session: Session | AsyncSession,
    settings: Settings | None = None,
) -> SearchRepository:
    """Return the search backend matching the configured database type."""
    settings = settings or get_settings()
    if settings.is_sqlite:
        return SqliteFtsSearchRepository(session)
    if settings.is_postgresql:
        return PgTsvectorSearchRepository(session)
    raise ValueError(f"Unsupported DATABASE_TYPE: {settings.DATABASE_TYPE!r}")
