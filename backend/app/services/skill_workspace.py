"""Filesystem skill workspace manager.

Layout (design.md §6.1):
  $DATA_ROOT/skills/<slug>__<skill_id>/
    SKILL.md
    skill.json
    versions/NNNN/SKILL.md
    assets/
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from app.config import Settings, get_settings

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
SYNC_KEYS = ("name", "description", "version", "tags", "author", "model")


class WorkspaceError(Exception):
    """Filesystem workspace failures."""


class SkillWorkspace:
    """Create / read / write skill packages on disk."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self.root = Path(self._settings.DATA_ROOT) / "skills"
        self.root.mkdir(parents=True, exist_ok=True)

    def package_dir(self, slug: str, skill_id: str) -> Path:
        return self.root / f"{slug}__{skill_id}"

    def create_package(
        self,
        *,
        slug: str,
        skill_id: str,
        name: str,
        description: str | None = None,
        version: int = 1,
        tags: list[Any] | None = None,
        author: str | None = None,
        model: str | None = None,
        body: str = "",
    ) -> Path:
        """Create the skill directory tree and write initial SKILL.md + skill.json."""
        pkg = self.package_dir(slug, skill_id)
        if pkg.exists():
            raise WorkspaceError(f"Package directory already exists: {pkg}")
        (pkg / "versions").mkdir(parents=True, exist_ok=True)
        (pkg / "assets").mkdir(parents=True, exist_ok=True)

        meta = {
            "name": name,
            "description": description or "",
            "version": version,
            "tags": tags or [],
            "author": author or "",
            "model": model or "",
        }
        content = render_skill_md(meta, body or f"# {name}\n")
        (pkg / "SKILL.md").write_text(content, encoding="utf-8")
        self._write_skill_json(pkg, meta)
        return pkg

    def read_skill_md(self, slug: str, skill_id: str) -> str:
        path = self.package_dir(slug, skill_id) / "SKILL.md"
        if not path.is_file():
            raise WorkspaceError(f"SKILL.md not found for {slug}__{skill_id}")
        return path.read_text(encoding="utf-8")

    def write_skill_md(self, slug: str, skill_id: str, content: str) -> None:
        pkg = self.package_dir(slug, skill_id)
        if not pkg.is_dir():
            raise WorkspaceError(f"Package not found: {pkg}")
        (pkg / "SKILL.md").write_text(content, encoding="utf-8")
        meta, _body = parse_skill_md(content)
        # Keep skill.json in sync with frontmatter
        existing = self.read_skill_json(slug, skill_id) if (pkg / "skill.json").is_file() else {}
        merged = {**existing, **{k: meta.get(k, existing.get(k)) for k in SYNC_KEYS if k in meta or k in existing}}
        for k in SYNC_KEYS:
            if k in meta:
                merged[k] = meta[k]
        self._write_skill_json(pkg, merged)

    def update_frontmatter(
        self,
        slug: str,
        skill_id: str,
        **fields: Any,
    ) -> str:
        """Update frontmatter keys in SKILL.md; returns new full content."""
        content = self.read_skill_md(slug, skill_id)
        meta, body = parse_skill_md(content)
        for key, value in fields.items():
            if key in SYNC_KEYS and value is not None:
                meta[key] = value
        new_content = render_skill_md(meta, body)
        self.write_skill_md(slug, skill_id, new_content)
        return new_content

    def create_version_snapshot(
        self,
        slug: str,
        skill_id: str,
        version_number: int,
    ) -> str:
        """Copy current SKILL.md into versions/NNNN/. Returns relative snapshot path."""
        pkg = self.package_dir(slug, skill_id)
        src = pkg / "SKILL.md"
        if not src.is_file():
            raise WorkspaceError("SKILL.md missing; cannot snapshot")
        folder = pkg / "versions" / f"{version_number:04d}"
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / "SKILL.md"
        shutil.copy2(src, dest)
        # Relative to package dir for storage in DB
        return f"versions/{version_number:04d}/SKILL.md"

    def delete_package(self, slug: str, skill_id: str) -> None:
        pkg = self.package_dir(slug, skill_id)
        if pkg.is_dir():
            shutil.rmtree(pkg)

    def read_skill_json(self, slug: str, skill_id: str) -> dict[str, Any]:
        path = self.package_dir(slug, skill_id) / "skill.json"
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_skill_json(self, pkg: Path, meta: dict[str, Any]) -> None:
        payload = {k: meta.get(k) for k in SYNC_KEYS}
        (pkg / "skill.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def parse_skill_md(content: str) -> tuple[dict[str, Any], str]:
    """Split SKILL.md into frontmatter dict + markdown body."""
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}, content
    raw = match.group(1)
    try:
        meta = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise WorkspaceError(f"Invalid YAML frontmatter: {exc}") from exc
    if not isinstance(meta, dict):
        meta = {}
    body = content[match.end() :]
    return meta, body


def render_skill_md(meta: dict[str, Any], body: str) -> str:
    """Render frontmatter + body into SKILL.md text."""
    # Prefer a stable key order
    ordered: dict[str, Any] = {}
    for key in SYNC_KEYS:
        if key in meta and meta[key] is not None:
            ordered[key] = meta[key]
    for key, value in meta.items():
        if key not in ordered and value is not None:
            ordered[key] = value
    fm = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, default_flow_style=False)
    body = body if body.endswith("\n") or body == "" else body + "\n"
    return f"---\n{fm}---\n{body}"
