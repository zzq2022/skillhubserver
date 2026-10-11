"""User / admin request & response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.user import UserRole


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=256)
    role: UserRole = UserRole.USER


class UpdateRoleRequest(BaseModel):
    role: UserRole


class UpdateStatusRequest(BaseModel):
    is_active: bool = Field(validation_alias="isActive", serialization_alias="isActive")

    model_config = {"populate_by_name": True}


class UserDetail(BaseModel):
    id: str
    username: str
    role: str
    is_active: bool = Field(serialization_alias="isActive")
    created_at: str = Field(serialization_alias="createdAt")
    updated_at: str = Field(serialization_alias="updatedAt")

    model_config = {"populate_by_name": True, "from_attributes": True}


class InstanceStats(BaseModel):
    users: int
    skills: int
    public_skills: int = Field(serialization_alias="publicSkills")
    pending_reviews: int = Field(serialization_alias="pendingReviews")
    online_clients: int = Field(default=0, serialization_alias="onlineClients")
    total_clients: int = Field(default=0, serialization_alias="totalClients")
    chat_sessions: int = Field(default=0, serialization_alias="chatSessions")

    model_config = {"populate_by_name": True}
