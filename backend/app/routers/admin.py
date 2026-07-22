"""Admin endpoints: user management + review workflow + instance stats."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.session_auth import AdminUser
from app.schemas.review import RejectReviewRequest, ReviewOut
from app.schemas.user import (
    CreateUserRequest,
    InstanceStats,
    UpdateRoleRequest,
    UpdateStatusRequest,
    UserDetail,
)
from app.services.review_service import ReviewService
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_detail(user) -> dict:  # noqa: ANN001
    return UserDetail(
        id=user.id,
        username=user.username,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else "",
        updated_at=user.updated_at.isoformat() if user.updated_at else "",
    ).model_dump(by_alias=True)


def _review_out(review) -> dict[str, Any]:  # noqa: ANN001
    skill_payload = None
    skill = getattr(review, "skill", None)
    if skill is not None:
        skill_payload = {
            "id": skill.id,
            "name": skill.name,
            "slug": skill.slug,
            "description": skill.description,
            "publishStatus": skill.publish_status.value
            if hasattr(skill.publish_status, "value")
            else str(skill.publish_status),
            "visibility": skill.visibility.value
            if hasattr(skill.visibility, "value")
            else str(skill.visibility),
            "ownerId": skill.owner_id,
        }
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
        skill=skill_payload,
    ).model_dump(by_alias=True)


@router.get("/users")
async def list_users(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    service = UserService(db)
    users = await service.list_users_async(offset=offset, limit=limit)
    return {"data": [_user_detail(u) for u in users]}


@router.post("/users", status_code=201)
async def create_user(
    body: CreateUserRequest,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    service = UserService(db)
    user = await service.create_user_async(
        username=body.username,
        password=body.password,
        role=body.role,
    )
    return {"data": _user_detail(user)}


@router.put("/users/{user_id}/role")
async def update_role(
    user_id: str,
    body: UpdateRoleRequest,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    service = UserService(db)
    user = await service.set_role_async(user_id, body.role)
    return {"data": _user_detail(user)}


@router.put("/users/{user_id}/status")
async def update_status(
    user_id: str,
    body: UpdateStatusRequest,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    service = UserService(db)
    user = await service.set_active_async(user_id, body.is_active)
    return {"data": _user_detail(user)}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    service = UserService(db)
    await service.delete_user_async(user_id)
    return {"data": {"ok": True}}


@router.get("/stats")
async def stats(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    service = UserService(db)
    raw = await service.stats_async()
    data = InstanceStats(
        users=raw["users"],
        skills=raw["skills"],
        public_skills=raw["public_skills"],
        pending_reviews=raw["pending_reviews"],
    )
    return {"data": data.model_dump(by_alias=True)}


@router.get("/reviews")
async def list_pending_reviews(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    service = ReviewService(db)
    items, total = await service.list_pending_async(offset=offset, limit=limit)
    return {
        "data": [_review_out(r) for r in items],
        "pagination": {
            "page": (offset // limit) + 1 if limit else 1,
            "pageSize": limit,
            "total": total,
        },
    }


@router.post("/reviews/{review_id}/approve")
async def approve_review(
    review_id: str,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    service = ReviewService(db)
    review = await service.approve_async(review_id, admin)
    return {"data": _review_out(review)}


@router.post("/reviews/{review_id}/reject")
async def reject_review(
    review_id: str,
    body: RejectReviewRequest,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    service = ReviewService(db)
    review = await service.reject_async(review_id, admin, comment=body.comment)
    return {"data": _review_out(review)}


def _skill_admin_out(skill, owner_username: str | None = None) -> dict[str, Any]:  # noqa: ANN001
    vis = skill.visibility.value if hasattr(skill.visibility, "value") else str(skill.visibility)
    pub = (
        skill.publish_status.value
        if hasattr(skill.publish_status, "value")
        else str(skill.publish_status)
    )
    is_public = vis == "public" and pub == "published"
    return {
        "id": skill.id,
        "name": skill.name,
        "slug": skill.slug,
        "description": skill.description or "",
        "category": skill.category,
        "visibility": vis,
        "publishStatus": pub,
        "isPublic": is_public,
        "featured": bool(skill.featured),
        "starCount": int(skill.star_count or 0),
        "downloadCount": int(skill.download_count or 0),
        "viewCount": int(skill.view_count or 0),
        "ownerId": skill.owner_id,
        "ownerUsername": owner_username,
        "updatedAt": skill.updated_at.isoformat() if skill.updated_at else None,
    }


@router.get("/skills")
async def list_skills(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(
        None,
        description="public|unpublished|pending|draft|rejected|private",
    ),
    q: str | None = Query(None),
) -> dict:
    from app.models.user import User

    service = ReviewService(db)
    items, total = await service.list_skills_async(
        offset=offset, limit=limit, status=status, q=q
    )
    owner_ids = {s.owner_id for s in items}
    owners: dict[str, str] = {}
    if owner_ids:
        from sqlalchemy import select

        result = await db.scalars(select(User).where(User.id.in_(owner_ids)))
        for u in result.all():
            owners[u.id] = u.username

    return {
        "data": [_skill_admin_out(s, owners.get(s.owner_id)) for s in items],
        "pagination": {
            "page": (offset // limit) + 1 if limit else 1,
            "pageSize": limit,
            "total": total,
        },
    }


@router.post("/skills/{skill_id}/unpublish")
async def unpublish_skill(
    skill_id: str,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    service = ReviewService(db)
    skill = await service.unpublish_async(skill_id, admin)
    return {"data": _skill_admin_out(skill)}


@router.post("/skills/{skill_id}/publish")
async def publish_skill(
    skill_id: str,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Admin force-publish (上架) without going through the review queue."""
    service = ReviewService(db)
    skill = await service.publish_async(skill_id, admin)
    return {"data": _skill_admin_out(skill)}
