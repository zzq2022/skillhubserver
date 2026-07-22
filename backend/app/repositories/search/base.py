"""Search repository abstract contract (design.md §3.7)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SkillSearchResult:
    """One hit from full-text search (ranked, with skill id for join)."""

    skill_id: str
    name: str
    description: str | None
    rank: float = 0.0


class SearchRepository(ABC):
    """Unified full-text search contract across SQLite FTS5 and PG tsvector.

    Implementations must:
    - Treat empty / whitespace-only query as "no results" (not an error).
    - Never raise on special characters / injection-like payloads.
    - Honour optional owner_id and visibility filters.
    - Not promise identical rank/order across backends.
    """

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        owner_id: str | None = None,
        visibility: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SkillSearchResult]:
        """Sync search (fixtures / simple scripts)."""

    @abstractmethod
    async def search_async(
        self,
        query: str,
        *,
        owner_id: str | None = None,
        visibility: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SkillSearchResult]:
        """Async search (FastAPI request path)."""

    @staticmethod
    def normalize_query(query: str | None) -> str:
        """Strip and collapse whitespace; empty means "no search"."""
        if not query:
            return ""
        return " ".join(query.split())


def sanitize_fts5_query(query: str) -> str:
    """Build a safe FTS5 MATCH expression for partial token matching.

    Strips FTS5 operators that would cause syntax errors, splits on hyphens
    (unicode61 tokenizer does the same when indexing), then joins tokens with
    AND and a prefix ``*`` so "skill" matches "my-skill" / "skillhub".
    """
    cleaned: list[str] = []
    for ch in query:
        if ch.isalnum() or ch in {"-", "_", " ", "."}:
            cleaned.append(ch)
        else:
            cleaned.append(" ")
    # Split on whitespace and hyphens/underscores to mirror FTS5 tokenization.
    rough = "".join(cleaned).replace("-", " ").replace("_", " ").replace(".", " ")
    tokens = [t for t in rough.split() if t]
    if not tokens:
        return ""
    safe_parts: list[str] = []
    for t in tokens:
        t = t.replace('"', "")
        if t:
            safe_parts.append(f'"{t}"*')
    return " AND ".join(safe_parts) if safe_parts else ""


def sanitize_tsquery_terms(query: str) -> list[str]:
    """Extract safe plain terms for PostgreSQL to_tsquery prefix matching."""
    cleaned: list[str] = []
    for ch in query:
        if ch.isalnum() or ch in {"-", "_", " ", "."}:
            cleaned.append(ch)
        else:
            cleaned.append(" ")
    rough = "".join(cleaned).replace("-", " ").replace("_", " ").replace(".", " ")
    return [t for t in rough.split() if t]
