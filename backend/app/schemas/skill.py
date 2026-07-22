"""Skill request & response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateSkillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    author: str | None = None
    model: str | None = None
    content: str | None = Field(
        default=None,
        description="Optional initial SKILL.md body (without frontmatter)",
    )


class UpdateSkillRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    tags: list[str] | None = None
    author: str | None = None
    model: str | None = None


class UpdateContentRequest(BaseModel):
    content: str = Field(min_length=1)


class CreateVersionRequest(BaseModel):
    notes: str | None = None


class SkillOut(BaseModel):
    id: str
    owner_id: str = Field(serialization_alias="ownerId")
    name: str
    slug: str
    description: str | None = None
    visibility: str
    publish_status: str = Field(serialization_alias="publishStatus")
    version: int
    tags: list[Any] = Field(default_factory=list)
    author: str | None = None
    model: str | None = None
    created_at: str = Field(serialization_alias="createdAt")
    updated_at: str = Field(serialization_alias="updatedAt")

    model_config = {"populate_by_name": True}


class SkillContentOut(BaseModel):
    content: str


class SkillVersionOut(BaseModel):
    id: str
    skill_id: str = Field(serialization_alias="skillId")
    version_number: int = Field(serialization_alias="versionNumber")
    snapshot_path: str = Field(serialization_alias="snapshotPath")
    notes: str | None = None
    created_at: str = Field(serialization_alias="createdAt")

    model_config = {"populate_by_name": True}
