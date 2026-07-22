"""SQLite FTS5 full-text search adapter."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.repositories.search.base import (
    SearchRepository,
    SkillSearchResult,
    sanitize_fts5_query,
)


class SqliteFtsSearchRepository(SearchRepository):
    """Search via `skills_fts` virtual table, joined back to `skills` for filters."""

    def __init__(self, session: Session | AsyncSession) -> None:
        self._session = session

    def search(
        self,
        query: str,
        *,
        owner_id: str | None = None,
        visibility: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SkillSearchResult]:
        assert isinstance(self._session, Session)
        q = self.normalize_query(query)
        if not q:
            return []
        match = sanitize_fts5_query(q)
        if not match:
            return []

        sql, params = self._build_sql(match, owner_id, visibility, limit, offset)
        rows = self._session.execute(text(sql), params).mappings().all()
        return [self._row_to_result(r) for r in rows]

    async def search_async(
        self,
        query: str,
        *,
        owner_id: str | None = None,
        visibility: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SkillSearchResult]:
        assert isinstance(self._session, AsyncSession)
        q = self.normalize_query(query)
        if not q:
            return []
        match = sanitize_fts5_query(q)
        if not match:
            return []

        sql, params = self._build_sql(match, owner_id, visibility, limit, offset)
        result = await self._session.execute(text(sql), params)
        rows = result.mappings().all()
        return [self._row_to_result(r) for r in rows]

    @staticmethod
    def _build_sql(
        match: str,
        owner_id: str | None,
        visibility: str | None,
        limit: int,
        offset: int,
    ) -> tuple[str, dict]:
        # bm25 lower is better; negate for "higher rank is better" contract.
        clauses = ["skills_fts MATCH :match"]
        params: dict = {
            "match": match,
            "limit": limit,
            "offset": offset,
        }
        if owner_id is not None:
            clauses.append("s.owner_id = :owner_id")
            params["owner_id"] = owner_id
        if visibility is not None:
            clauses.append("s.visibility = :visibility")
            params["visibility"] = visibility

        where = " AND ".join(clauses)
        sql = f"""
            SELECT
                s.id AS skill_id,
                s.name AS name,
                s.description AS description,
                -bm25(skills_fts) AS rank
            FROM skills_fts
            JOIN skills s ON s.id = skills_fts.skill_id
            WHERE {where}
            ORDER BY rank DESC
            LIMIT :limit OFFSET :offset
        """
        return sql, params

    @staticmethod
    def _row_to_result(row: Any) -> SkillSearchResult:
        return SkillSearchResult(
            skill_id=row["skill_id"],
            name=row["name"],
            description=row["description"],
            rank=float(row["rank"] or 0.0),
        )
