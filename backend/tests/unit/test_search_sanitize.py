"""Unit tests for search query sanitizers."""

from __future__ import annotations

from app.repositories.search.base import (
    SearchRepository,
    sanitize_fts5_query,
    sanitize_tsquery_terms,
)


def test_normalize_query() -> None:
    assert SearchRepository.normalize_query(None) == ""  # type: ignore[arg-type]
    assert SearchRepository.normalize_query("  a   b  ") == "a b"


def test_fts5_prefix_and_and() -> None:
    q = sanitize_fts5_query("my skill")
    assert '"my"*' in q
    assert '"skill"*' in q
    assert "AND" in q


def test_fts5_strips_operators() -> None:
    q = sanitize_fts5_query('foo" OR bar')
    assert "OR" not in q or '"or"*' in q.lower()
    # Double quotes stripped from tokens
    assert '""' not in q


def test_tsquery_terms_split_hyphen() -> None:
    assert sanitize_tsquery_terms("my-skill") == ["my", "skill"]
