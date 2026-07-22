"""Media upload / get / delete endpoints (design.md §4.8)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.middleware.session_auth import CurrentUser
from app.schemas.media import MediaOut
from app.services.media_service import MediaService

router = APIRouter(prefix="/media", tags=["media"])


def _media_out(media) -> dict[str, Any]:  # noqa: ANN001
    return MediaOut(
        id=media.id,
        owner_id=media.owner_id,
        filename=media.filename,
        content_type=media.content_type,
        size_bytes=media.size_bytes,
        created_at=media.created_at.isoformat() if media.created_at else "",
    ).model_dump(by_alias=True)


@router.post("/upload", status_code=201)
async def upload_media(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
) -> dict:
    service = MediaService(db, settings)
    media = await service.upload_async(
        user,
        file.file,
        filename=file.filename,
        content_type=file.content_type,
        size_hint=file.size,
    )
    return {"data": _media_out(media)}


@router.get("/{media_id}")
async def get_media(
    media_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    service = MediaService(db, settings)
    media, data = await service.read_bytes_async(media_id, user)
    return Response(
        content=data,
        media_type=media.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{media.filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.delete("/{media_id}")
async def delete_media(
    media_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = MediaService(db, settings)
    await service.delete_async(media_id, user)
    return {"data": {"ok": True}}
