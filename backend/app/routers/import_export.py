"""Skill ZIP import / export endpoints (design.md §4.7)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.middleware.session_auth import CurrentUser
from app.schemas.skill import SkillOut
from app.services.import_export_service import ImportExportService

router = APIRouter(tags=["import-export"])


def _skill_out(skill) -> dict[str, Any]:  # noqa: ANN001
    return SkillOut(
        id=skill.id,
        owner_id=skill.owner_id,
        name=skill.name,
        slug=skill.slug,
        description=skill.description,
        visibility=skill.visibility.value
        if hasattr(skill.visibility, "value")
        else str(skill.visibility),
        publish_status=skill.publish_status.value
        if hasattr(skill.publish_status, "value")
        else str(skill.publish_status),
        version=skill.version,
        tags=list(skill.tags or []),
        author=skill.author,
        model=skill.model,
        created_at=skill.created_at.isoformat() if skill.created_at else "",
        updated_at=skill.updated_at.isoformat() if skill.updated_at else "",
    ).model_dump(by_alias=True)


@router.post("/skills/import", status_code=201)
async def import_skill(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
) -> dict:
    service = ImportExportService(db, settings)
    skill = await service.import_async(
        user,
        file.file,
        filename=file.filename,
        size_hint=file.size,
    )
    return {"data": _skill_out(skill)}


@router.get("/skills/{skill_id}/export")
async def export_skill(
    skill_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    service = ImportExportService(db, settings)
    data, filename = await service.export_async(skill_id, user)
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
