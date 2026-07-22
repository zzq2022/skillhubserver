"""Bootstrap endpoints: first-run admin creation."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.routers.auth import _set_session_cookie
from app.schemas.auth import BootstrapInitRequest, BootstrapStatus, LoginData, UserPublic
from app.services.auth_service import AuthService

router = APIRouter(prefix="/bootstrap", tags=["bootstrap"])


@router.get("")
async def bootstrap_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = AuthService(db, settings)
    initialized, registration_closed = await service.bootstrap_status_async()
    data = BootstrapStatus(
        initialized=initialized,
        registration_closed=registration_closed,
    )
    return {"data": data.model_dump(by_alias=True)}


@router.post("/init")
async def bootstrap_init(
    body: BootstrapInitRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = AuthService(db, settings)
    result = await service.bootstrap_init_async(body.username, body.password)
    _set_session_cookie(response, settings, result.session_id)
    data = LoginData(
        user=UserPublic.model_validate(result.user),
        csrf_token=result.csrf_token,
    )
    return {"data": data.model_dump(by_alias=True)}
