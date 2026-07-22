"""Shared response envelope helpers."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class DataResponse(BaseModel, Generic[T]):
    data: T


class Pagination(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, serialization_alias="pageSize")
    total: int = Field(ge=0)

    model_config = {"populate_by_name": True}


class ListResponse(BaseModel, Generic[T]):
    data: list[T]
    pagination: Pagination | None = None
