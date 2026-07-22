"""AgentWork-compatible SkillHub routes at /api/skillhub/* for Hope clients."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.middleware.dual_auth import DualUser, optional_dual_user
from app.models.user import User
from app.services.compat_skillhub_service import CompatSkillHubService

router = APIRouter(prefix="/skillhub", tags=["compat-skillhub"])


class ReviewSubmissionBody(BaseModel):
    fileName: str = Field(min_length=1, max_length=260)
    packageBase64: str = Field(min_length=1)
    localSkillId: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=10000)
    version: str | None = Field(default=None, max_length=50)
    author: str | None = Field(default=None, max_length=120)
    tags: list[str] | None = None
    category: str | None = None
    directoryFingerprint: str | None = Field(default=None, max_length=256)


@router.get("/public")
async def browse_public(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    actor: Annotated[User | None, Depends(optional_dual_user)],
    page: int = Query(1, ge=1),
    sort: str | None = Query(None),
    category: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=100),
) -> dict:
    svc = CompatSkillHubService(db, settings)
    page_size = limit or 20
    data = await svc.browse_public(
        page=page,
        page_size=page_size,
        sort=sort,
        category=category,
        actor_id=actor.id if actor else None,
    )
    return {"data": data}


@router.get("/public/search")
async def search_public(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    actor: Annotated[User | None, Depends(optional_dual_user)],
    q: str = Query(""),
    page: int = Query(1, ge=1),
    sort: str | None = Query(None),
    category: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=100),
) -> dict:
    svc = CompatSkillHubService(db, settings)
    page_size = limit or 20
    data = await svc.browse_public(
        page=page,
        page_size=page_size,
        sort=sort,
        category=category,
        q=q,
        actor_id=actor.id if actor else None,
    )
    return {"data": data}


@router.get("/public/stats")
async def public_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    svc = CompatSkillHubService(db, settings)
    return {"data": await svc.marketplace_stats()}


@router.get("/public/featured")
async def public_featured(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(6, ge=1, le=50),
) -> dict:
    svc = CompatSkillHubService(db, settings)
    return {"data": await svc.featured_skills(limit)}


@router.get("/public/{skill_id}")
async def public_detail(
    skill_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    actor: Annotated[User | None, Depends(optional_dual_user)],
) -> dict:
    svc = CompatSkillHubService(db, settings)
    data = await svc.get_public_detail(skill_id, actor_id=actor.id if actor else None)
    return {"data": data}


@router.post("/public/{skill_id}/star")
async def star_skill(
    skill_id: str,
    user: DualUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    svc = CompatSkillHubService(db, settings)
    return {"data": await svc.toggle_star(user, skill_id)}


@router.post("/public/{skill_id}/view")
async def view_skill(
    skill_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    svc = CompatSkillHubService(db, settings)
    await svc.increment_view(skill_id)
    return {"data": {"ok": True}}


@router.get("/private")
async def list_private(
    user: DualUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    svc = CompatSkillHubService(db, settings)
    return {"data": await svc.list_private(user)}


@router.get("/private/{skill_id}")
async def private_detail(
    skill_id: str,
    user: DualUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    svc = CompatSkillHubService(db, settings)
    return {"data": await svc.get_private_detail(user, skill_id)}


@router.post("/review-submissions")
async def review_submissions(
    body: ReviewSubmissionBody,
    user: DualUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    svc = CompatSkillHubService(db, settings)
    data = await svc.submit_review_package(
        user,
        file_name=body.fileName,
        package_base64=body.packageBase64,
        name=body.name,
        description=body.description,
        category=body.category,
        tags=body.tags,
        author=body.author,
    )
    return {"data": data}


@router.get("/{skill_id}/download")
async def download_skill(
    skill_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    actor: Annotated[User | None, Depends(optional_dual_user)],
) -> Response:
    svc = CompatSkillHubService(db, settings)
    data, filename = await svc.download_zip(skill_id, actor)
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str,
    user: DualUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    svc = CompatSkillHubService(db, settings)
    return {"data": await svc.delete_skill(user, skill_id)}
