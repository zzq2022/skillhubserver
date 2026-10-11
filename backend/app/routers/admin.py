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
        online_clients=raw.get("online_clients", 0),
        total_clients=raw.get("total_clients", 0),
        chat_sessions=raw.get("chat_sessions", 0),
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


# ---- Client Tracking & Session Auditing Endpoints --------------------------

@router.get("/clients")
async def list_clients(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None),
) -> dict:
    import json
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, func, or_
    from app.models.client_instance import ClientInstance
    from app.models.client_chat_session import ClientChatSession
    from app.models.user import User

    now = datetime.now(timezone.utc)
    online_threshold = now - timedelta(seconds=180)

    total_count = await db.scalar(select(func.count()).select_from(ClientInstance)) or 0
    online_count = (
        await db.scalar(
            select(func.count())
            .select_from(ClientInstance)
            .where(ClientInstance.last_heartbeat_at >= online_threshold)
        )
        or 0
    )

    query = (
        select(ClientInstance, User.username)
        .outerjoin(User, ClientInstance.user_id == User.id)
        .order_by(ClientInstance.last_heartbeat_at.desc())
    )

    if q:
        kw = f"%{q.strip()}%"
        query = query.where(
            or_(
                ClientInstance.machine_name.ilike(kw),
                ClientInstance.id.ilike(kw),
                ClientInstance.os_platform.ilike(kw),
                User.username.ilike(kw),
            )
        )

    items_stmt = query.offset(offset).limit(limit)
    res = await db.execute(items_stmt)
    rows = res.all()

    inst_ids = [inst.id for inst, _ in rows]
    session_counts: dict[str, int] = {}
    if inst_ids:
        cnt_stmt = (
            select(ClientChatSession.client_instance_id, func.count(ClientChatSession.id))
            .where(ClientChatSession.client_instance_id.in_(inst_ids))
            .group_by(ClientChatSession.client_instance_id)
        )
        cnt_res = await db.execute(cnt_stmt)
        for i_id, c in cnt_res.all():
            session_counts[i_id] = c

    items = []
    for inst, username in rows:
        last_hb = inst.last_heartbeat_at
        if last_hb and last_hb.tzinfo is None:
            last_hb = last_hb.replace(tzinfo=timezone.utc)
        is_online = (last_hb >= online_threshold) if last_hb else False
        items.append({
            "id": inst.id,
            "machineName": inst.machine_name or "未知设备",
            "osPlatform": inst.os_platform or "unknown",
            "appVersion": inst.app_version or "0.0.1",
            "hostVersion": inst.host_version or "",
            "ipAddress": inst.ip_address or "",
            "userId": inst.user_id,
            "username": username or "未登录",
            "isOnline": is_online,
            "status": "online" if is_online else "offline",
            "lastHeartbeatAt": inst.last_heartbeat_at.isoformat() if inst.last_heartbeat_at else None,
            "createdAt": inst.created_at.isoformat() if inst.created_at else None,
            "sessionCount": session_counts.get(inst.id, 0),
        })

    return {
        "data": {
            "onlineCount": online_count,
            "totalCount": total_count,
            "items": items,
        },
        "pagination": {
            "page": (offset // limit) + 1 if limit else 1,
            "pageSize": limit,
            "total": total_count,
        },
    }


@router.get("/chat-sessions")
async def list_chat_sessions(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    clientId: str | None = Query(None),
    userId: str | None = Query(None),
    q: str | None = Query(None),
) -> dict:
    from sqlalchemy import select, func, or_
    from app.models.client_chat_session import ClientChatSession
    from app.models.client_instance import ClientInstance
    from app.models.user import User

    query = (
        select(ClientChatSession, User.username, ClientInstance.machine_name)
        .outerjoin(User, ClientChatSession.user_id == User.id)
        .outerjoin(ClientInstance, ClientChatSession.client_instance_id == ClientInstance.id)
        .order_by(ClientChatSession.session_updated_at.desc())
    )

    if clientId:
        query = query.where(ClientChatSession.client_instance_id == clientId)
    if userId:
        query = query.where(ClientChatSession.user_id == userId)
    if q:
        kw = f"%{q.strip()}%"
        query = query.where(
            or_(
                ClientChatSession.title.ilike(kw),
                ClientChatSession.workspace_name.ilike(kw),
                ClientChatSession.session_key.ilike(kw),
                User.username.ilike(kw),
            )
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    res = await db.execute(query.offset(offset).limit(limit))
    rows = res.all()

    items = []
    for sess, username, machine_name in rows:
        items.append({
            "id": sess.id,
            "sessionKey": sess.session_key,
            "instanceId": sess.client_instance_id,
            "machineName": machine_name or "未知设备",
            "userId": sess.user_id,
            "username": username or "未登录",
            "title": sess.title,
            "workspaceName": sess.workspace_name or "默认工作区",
            "workspacePath": sess.workspace_path or "",
            "totalTokens": sess.total_tokens,
            "messageCount": sess.message_count,
            "sessionCreatedAt": sess.session_created_at.isoformat() if sess.session_created_at else None,
            "sessionUpdatedAt": sess.session_updated_at.isoformat() if sess.session_updated_at else None,
            "updatedAt": sess.updated_at.isoformat() if sess.updated_at else None,
        })

    return {
        "data": items,
        "pagination": {
            "page": (offset // limit) + 1 if limit else 1,
            "pageSize": limit,
            "total": total,
        },
    }


@router.get("/chat-sessions/{session_id}")
async def get_chat_session_detail(
    session_id: str,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    import json
    from sqlalchemy import select
    from fastapi import HTTPException
    from app.models.client_chat_session import ClientChatSession
    from app.models.client_instance import ClientInstance
    from app.models.user import User

    stmt = (
        select(ClientChatSession, User.username, ClientInstance.machine_name)
        .outerjoin(User, ClientChatSession.user_id == User.id)
        .outerjoin(ClientInstance, ClientChatSession.client_instance_id == ClientInstance.id)
        .where(ClientChatSession.id == session_id)
    )
    res = await db.execute(stmt)
    row = res.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Chat session not found")

    sess, username, machine_name = row
    messages = []
    if sess.messages_json:
        try:
            messages = json.loads(sess.messages_json)
        except Exception:
            messages = []

    return {
        "data": {
            "id": sess.id,
            "sessionKey": sess.session_key,
            "instanceId": sess.client_instance_id,
            "machineName": machine_name or "未知设备",
            "userId": sess.user_id,
            "username": username or "未登录",
            "title": sess.title,
            "workspaceName": sess.workspace_name or "默认工作区",
            "workspacePath": sess.workspace_path or "",
            "totalTokens": sess.total_tokens,
            "messageCount": sess.message_count,
            "sessionCreatedAt": sess.session_created_at.isoformat() if sess.session_created_at else None,
            "sessionUpdatedAt": sess.session_updated_at.isoformat() if sess.session_updated_at else None,
            "messages": messages,
        }
    }
