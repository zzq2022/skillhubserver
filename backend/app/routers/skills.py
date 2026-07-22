"""Private skills CRUD + content + versions endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.middleware.session_auth import CurrentUser
from app.schemas.skill import (
    CreateSkillRequest,
    CreateVersionRequest,
    SkillContentOut,
    SkillOut,
    SkillVersionOut,
    UpdateContentRequest,
    UpdateSkillRequest,
)
from app.schemas.review import ReviewOut
from app.services.review_service import ReviewService
from app.services.skill_service import SkillService

router = APIRouter(prefix="/skills", tags=["skills"])


def _review_out(review) -> dict[str, Any]:  # noqa: ANN001
    return ReviewOut(
        id=review.id,
        skill_id=review.skill_id,
        submitter_id=review.submitter_id,
        reviewer_id=review.reviewer_id,
        status=review.status.value
        if hasattr(review.status, "value")
        else str(review.status),
        comment=review.comment,
        submitted_at=review.submitted_at.isoformat() if review.submitted_at else "",
        reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None,
    ).model_dump(by_alias=True)


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


def _version_out(v) -> dict[str, Any]:  # noqa: ANN001
    return SkillVersionOut(
        id=v.id,
        skill_id=v.skill_id,
        version_number=v.version_number,
        snapshot_path=v.snapshot_path,
        notes=v.notes,
        created_at=v.created_at.isoformat() if v.created_at else "",
    ).model_dump(by_alias=True)


@router.get("")
async def list_skills(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None),
) -> dict:
    service = SkillService(db, settings)
    skills, total = await service.list_skills_async(
        user, offset=offset, limit=limit, q=q
    )
    return {
        "data": [_skill_out(s) for s in skills],
        "pagination": {
            "page": (offset // limit) + 1 if limit else 1,
            "pageSize": limit,
            "total": total,
        },
    }


@router.post("", status_code=201)
async def create_skill(
    body: CreateSkillRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = SkillService(db, settings)
    skill = await service.create_skill_async(
        user,
        name=body.name,
        description=body.description,
        tags=body.tags,
        author=body.author,
        model=body.model,
        content=body.content,
    )
    return {"data": _skill_out(skill)}


@router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = SkillService(db, settings)
    skill = await service.get_skill_async(skill_id, user)
    return {"data": _skill_out(skill)}


@router.put("/{skill_id}")
async def update_skill(
    skill_id: str,
    body: UpdateSkillRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = SkillService(db, settings)
    skill = await service.update_skill_async(
        skill_id,
        user,
        name=body.name,
        description=body.description,
        tags=body.tags,
        author=body.author,
        model=body.model,
    )
    return {"data": _skill_out(skill)}


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = SkillService(db, settings)
    await service.delete_skill_async(skill_id, user)
    return {"data": {"ok": True}}


@router.get("/{skill_id}/content")
async def get_content(
    skill_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = SkillService(db, settings)
    content = await service.get_content_async(skill_id, user)
    return {"data": SkillContentOut(content=content).model_dump()}


@router.put("/{skill_id}/content")
async def update_content(
    skill_id: str,
    body: UpdateContentRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = SkillService(db, settings)
    content = await service.update_content_async(skill_id, user, body.content)
    return {"data": SkillContentOut(content=content).model_dump()}


@router.get("/{skill_id}/versions")
async def list_versions(
    skill_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = SkillService(db, settings)
    versions = await service.list_versions_async(skill_id, user)
    return {"data": [_version_out(v) for v in versions]}


@router.post("/{skill_id}/versions", status_code=201)
async def create_version(
    skill_id: str,
    body: CreateVersionRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = SkillService(db, settings)
    version = await service.create_version_async(skill_id, user, notes=body.notes)
    return {"data": _version_out(version)}


@router.post("/{skill_id}/submit", status_code=200)
async def submit_for_review(
    skill_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Owner submits skill for publish review."""
    service = ReviewService(db)
    review = await service.submit_async(skill_id, user)
    return {"data": _review_out(review)}
