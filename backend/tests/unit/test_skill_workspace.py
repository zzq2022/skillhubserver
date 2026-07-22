"""Unit tests for SkillWorkspace frontmatter sync (T4.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.services.skill_workspace import (
    SkillWorkspace,
    parse_skill_md,
    render_skill_md,
)


@pytest.fixture
def workspace(tmp_path: Path) -> SkillWorkspace:
    settings = Settings(
        SECRET_KEY="ws-test",
        DATA_ROOT=str(tmp_path),
        DATABASE_URL="sqlite:///:memory:",
    )
    return SkillWorkspace(settings)


def test_parse_and_render_roundtrip() -> None:
    content = render_skill_md(
        {"name": "demo", "description": "d", "version": 1, "tags": ["t"]},
        "# Body\n",
    )
    meta, body = parse_skill_md(content)
    assert meta["name"] == "demo"
    assert meta["tags"] == ["t"]
    assert body.strip() == "# Body"


def test_create_package_and_snapshot(workspace: SkillWorkspace) -> None:
    pkg = workspace.create_package(
        slug="demo",
        skill_id="uuid-1",
        name="demo",
        description="hello",
        tags=["a"],
        body="# Demo\n",
    )
    assert (pkg / "SKILL.md").is_file()
    assert (pkg / "skill.json").is_file()
    assert (pkg / "versions").is_dir()

    path = workspace.create_version_snapshot("demo", "uuid-1", 1)
    assert path == "versions/0001/SKILL.md"
    assert (pkg / "versions" / "0001" / "SKILL.md").is_file()

    workspace.update_frontmatter("demo", "uuid-1", description="updated")
    content = workspace.read_skill_md("demo", "uuid-1")
    meta, _ = parse_skill_md(content)
    assert meta["description"] == "updated"

    workspace.delete_package("demo", "uuid-1")
    assert not pkg.exists()
