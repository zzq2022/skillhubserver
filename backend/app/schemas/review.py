"""Review / hub request & response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RejectReviewRequest(BaseModel):
    comment: str | None = None


class ReviewOut(BaseModel):
    id: str
    skill_id: str = Field(serialization_alias="skillId")
    submitter_id: str = Field(serialization_alias="submitterId")
    reviewer_id: str | None = Field(default=None, serialization_alias="reviewerId")
    status: str
    comment: str | None = None
    submitted_at: str = Field(serialization_alias="submittedAt")
    reviewed_at: str | None = Field(default=None, serialization_alias="reviewedAt")
    skill: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class HubSkillOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    tags: list[Any] = Field(default_factory=list)
    author: str | None = None
    model: str | None = None
    version: int
    owner: str
    updated_at: str = Field(serialization_alias="updatedAt")

    model_config = {"populate_by_name": True}
