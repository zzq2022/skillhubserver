"""Auth / bootstrap request & response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(
        min_length=1,
        max_length=256,
        validation_alias="currentPassword",
    )
    new_password: str = Field(
        min_length=8,
        max_length=256,
        validation_alias="newPassword",
    )

    model_config = {"populate_by_name": True}


class UserPublic(BaseModel):
    id: str
    username: str
    role: str
    is_active: bool = Field(serialization_alias="isActive")

    model_config = {"from_attributes": True, "populate_by_name": True}


class LoginData(BaseModel):
    user: UserPublic
    csrf_token: str = Field(serialization_alias="csrfToken")

    model_config = {"populate_by_name": True}


class BootstrapStatus(BaseModel):
    initialized: bool
    registration_closed: bool = Field(serialization_alias="registrationClosed")

    model_config = {"populate_by_name": True}


class BootstrapInitRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=256)
