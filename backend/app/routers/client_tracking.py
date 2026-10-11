"""Client instance heartbeat & session synchronization endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.dual_auth import DualUser, OptionalDualUser
from app.models.client_chat_session import ClientChatSession
from app.models.client_instance import ClientInstance

router = APIRouter(prefix="/client", tags=["client-tracking"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_datetime(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        clean_val = val.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_val)
    except Exception:
        return None


class ClientHeartbeatRequest(BaseModel):
    instanceId: str = Field(min_length=1, max_length=64)
    machineName: str | None = None
    osPlatform: str | None = None
    appVersion: str | None = None
    hostVersion: str | None = None
    endpointUrl: str | None = None


class SessionSyncItem(BaseModel):
    sessionKey: str = Field(min_length=1, max_length=128)
    instanceId: str = Field(min_length=1, max_length=64)
    title: str = "未命名会话"
    workspaceName: str | None = None
    workspacePath: str | None = None
    totalTokens: int = 0
    messageCount: int = 0
    sessionCreatedAt: str | None = None
    sessionUpdatedAt: str | None = None
    messages: list[dict[str, Any]] | None = None


class SessionSyncBatchRequest(BaseModel):
    instanceId: str = Field(min_length=1, max_length=64)
    sessions: list[SessionSyncItem]


@router.post("/heartbeat")
async def client_heartbeat(
    request: Request,
    body: ClientHeartbeatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: OptionalDualUser,
) -> dict:
    now = _utcnow()
    ip_address = request.client.host if request.client else None

    stmt = select(ClientInstance).where(ClientInstance.id == body.instanceId)
    res = await db.execute(stmt)
    instance = res.scalar_one_or_none()

    if instance is None:
        instance = ClientInstance(
            id=body.instanceId,
            machine_name=body.machineName,
            os_platform=body.osPlatform,
            app_version=body.appVersion,
            host_version=body.hostVersion,
            endpoint_url=body.endpointUrl,
            ip_address=ip_address,
            user_id=actor.id if actor else None,
            status="online",
            last_heartbeat_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(instance)
    else:
        instance.last_heartbeat_at = now
        instance.status = "online"
        instance.updated_at = now
        if body.machineName:
            instance.machine_name = body.machineName
        if body.osPlatform:
            instance.os_platform = body.osPlatform
        if body.appVersion:
            instance.app_version = body.appVersion
        if body.hostVersion:
            instance.host_version = body.hostVersion
        if body.endpointUrl:
            instance.endpoint_url = body.endpointUrl
        if ip_address:
            instance.ip_address = ip_address
        if actor:
            instance.user_id = actor.id

    await db.commit()
    await db.refresh(instance)

    return {
        "data": {
            "status": "ok",
            "instanceId": instance.id,
            "isOnline": True,
            "lastHeartbeatAt": instance.last_heartbeat_at.isoformat(),
        }
    }


@router.post("/sessions/sync")
async def client_sessions_sync(
    body: SessionSyncBatchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: DualUser,
) -> dict:
    now = _utcnow()

    stmt = select(ClientInstance).where(ClientInstance.id == body.instanceId)
    res = await db.execute(stmt)
    instance = res.scalar_one_or_none()

    if instance is None:
        instance = ClientInstance(
            id=body.instanceId,
            user_id=actor.id,
            status="online",
            last_heartbeat_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(instance)
        await db.flush()
    else:
        instance.user_id = actor.id
        instance.last_heartbeat_at = now

    synced_count = 0
    for item in body.sessions:
        unique_id = f"{item.instanceId}::{item.sessionKey}"
        stmt_session = select(ClientChatSession).where(ClientChatSession.id == unique_id)
        res_session = await db.execute(stmt_session)
        chat_sess = res_session.scalar_one_or_none()

        sess_created = _parse_iso_datetime(item.sessionCreatedAt)
        sess_updated = _parse_iso_datetime(item.sessionUpdatedAt)
        messages_blob = json.dumps(item.messages, ensure_ascii=False) if item.messages else None

        if chat_sess is None:
            chat_sess = ClientChatSession(
                id=unique_id,
                session_key=item.sessionKey,
                client_instance_id=body.instanceId,
                user_id=actor.id,
                title=item.title or "未命名会话",
                workspace_name=item.workspaceName,
                workspace_path=item.workspacePath,
                total_tokens=item.totalTokens,
                message_count=item.messageCount or (len(item.messages) if item.messages else 0),
                session_created_at=sess_created,
                session_updated_at=sess_updated or now,
                messages_json=messages_blob,
                created_at=now,
                updated_at=now,
            )
            db.add(chat_sess)
        else:
            chat_sess.user_id = actor.id
            chat_sess.title = item.title or chat_sess.title
            if item.workspaceName:
                chat_sess.workspace_name = item.workspaceName
            if item.workspacePath:
                chat_sess.workspace_path = item.workspacePath
            chat_sess.total_tokens = item.totalTokens
            chat_sess.message_count = item.messageCount or (len(item.messages) if item.messages else chat_sess.message_count)
            if sess_updated:
                chat_sess.session_updated_at = sess_updated
            if messages_blob:
                chat_sess.messages_json = messages_blob
            chat_sess.updated_at = now

        synced_count += 1

    await db.commit()

    return {
        "data": {
            "status": "ok",
            "syncedCount": synced_count,
        }
    }
