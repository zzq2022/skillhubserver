"""Media request & response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MediaOut(BaseModel):
    id: str
    owner_id: str = Field(serialization_alias="ownerId")
    filename: str
    content_type: str = Field(serialization_alias="contentType")
    size_bytes: int = Field(serialization_alias="sizeBytes")
    created_at: str = Field(serialization_alias="createdAt")

    model_config = {"populate_by_name": True}
