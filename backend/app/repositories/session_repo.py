"""Session repository — CRUD and expiry cleanup."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.models.session import Session as SessionModel
from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionRepository:
    """Data access for the `sessions` table."""

    def __init__(self, session: Session | AsyncSession) -> None:
        self._session = session

    # ---- sync -------------------------------------------------------------

    def get_by_id(self, session_id: str) -> SessionModel | None:
        assert isinstance(self._session, Session)
        return self._session.get(SessionModel, session_id)

    def get_with_user(self, session_id: str) -> SessionModel | None:
        assert isinstance(self._session, Session)
        stmt = (
            select(SessionModel)
            .where(SessionModel.id == session_id)
            .options(selectinload(SessionModel.user))
        )
        return self._session.scalars(stmt).first()

    def create(
        self,
        *,
        session_id: str,
        user_id: str,
        csrf_token: str,
        expires_at: datetime,
        last_active_at: datetime | None = None,
    ) -> SessionModel:
        assert isinstance(self._session, Session)
        now = last_active_at or _utcnow()
        row = SessionModel(
            id=session_id,
            user_id=user_id,
            csrf_token=csrf_token,
            expires_at=expires_at,
            last_active_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def delete(self, session_id: str) -> bool:
        assert isinstance(self._session, Session)
        row = self.get_by_id(session_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True

    def delete_for_user(self, user_id: str) -> int:
        """Revoke all sessions for a user (logout-all / disable user)."""
        assert isinstance(self._session, Session)
        result = self._session.execute(
            delete(SessionModel).where(SessionModel.user_id == user_id)
        )
        self._session.flush()
        return result.rowcount or 0

    def cleanup_expired(self, now: datetime | None = None) -> int:
        """Delete sessions past absolute expiry. Returns rows removed."""
        assert isinstance(self._session, Session)
        now = now or _utcnow()
        result = self._session.execute(
            delete(SessionModel).where(SessionModel.expires_at < now)
        )
        self._session.flush()
        return result.rowcount or 0

    def touch(self, row: SessionModel, now: datetime | None = None) -> None:
        assert isinstance(self._session, Session)
        row.last_active_at = now or _utcnow()
        self._session.flush()

    # ---- async ------------------------------------------------------------

    async def get_by_id_async(self, session_id: str) -> SessionModel | None:
        assert isinstance(self._session, AsyncSession)
        return await self._session.get(SessionModel, session_id)

    async def get_with_user_async(self, session_id: str) -> SessionModel | None:
        assert isinstance(self._session, AsyncSession)
        stmt = (
            select(SessionModel)
            .where(SessionModel.id == session_id)
            .options(selectinload(SessionModel.user))
        )
        result = await self._session.scalars(stmt)
        return result.first()

    async def create_async(
        self,
        *,
        session_id: str,
        user_id: str,
        csrf_token: str,
        expires_at: datetime,
        last_active_at: datetime | None = None,
    ) -> SessionModel:
        assert isinstance(self._session, AsyncSession)
        now = last_active_at or _utcnow()
        row = SessionModel(
            id=session_id,
            user_id=user_id,
            csrf_token=csrf_token,
            expires_at=expires_at,
            last_active_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def delete_async(self, session_id: str) -> bool:
        assert isinstance(self._session, AsyncSession)
        row = await self.get_by_id_async(session_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def delete_for_user_async(self, user_id: str) -> int:
        assert isinstance(self._session, AsyncSession)
        result = await self._session.execute(
            delete(SessionModel).where(SessionModel.user_id == user_id)
        )
        await self._session.flush()
        return result.rowcount or 0

    async def cleanup_expired_async(self, now: datetime | None = None) -> int:
        assert isinstance(self._session, AsyncSession)
        now = now or _utcnow()
        result = await self._session.execute(
            delete(SessionModel).where(SessionModel.expires_at < now)
        )
        await self._session.flush()
        return result.rowcount or 0

    async def touch_async(self, row: SessionModel, now: datetime | None = None) -> None:
        assert isinstance(self._session, AsyncSession)
        row.last_active_at = now or _utcnow()
        await self._session.flush()
