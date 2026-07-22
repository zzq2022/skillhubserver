"""Skill name validation and slugify helpers."""

from __future__ import annotations

import re

# Per design: /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/
SKILL_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_NON_SLUG = re.compile(r"[^a-z0-9]+")
_MULTI_DASH = re.compile(r"-{2,}")


def is_valid_skill_name(name: str) -> bool:
    """Return True if `name` matches the skill name regex."""
    if not name or len(name) > 100:
        return False
    return bool(SKILL_NAME_RE.match(name))


def validate_skill_name(name: str) -> str:
    """Return `name` if valid, else raise ValueError."""
    if not is_valid_skill_name(name):
        raise ValueError(
            "Skill name must be lowercase alphanumeric with optional hyphens, "
            "start and end with a letter or digit, and be at most 100 chars"
        )
    return name


def slugify(name: str) -> str:
    """Derive a filesystem/URL-safe slug from a free-form display name.

    If the input already looks like a valid skill name, return it as-is.
    Otherwise lower-case, replace non-alnum runs with '-', strip edges.
    """
    raw = (name or "").strip().lower()
    if is_valid_skill_name(raw):
        return raw
    slug = _NON_SLUG.sub("-", raw)
    slug = _MULTI_DASH.sub("-", slug).strip("-")
    if not slug:
        raise ValueError("Cannot derive a valid skill slug from the given name")
    if len(slug) > 100:
        slug = slug[:100].rstrip("-")
    if not is_valid_skill_name(slug):
        # Single-char or still invalid after truncation
        if len(slug) == 1 and slug.isalnum():
            return slug
        raise ValueError(f"Derived slug is invalid: {slug!r}")
    return slug
