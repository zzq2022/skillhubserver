"""Media repository — uploaded asset records."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.media import Media


class MediaRepository:
    def __init__(self, session: Session | AsyncSession) -> None:
        self._session = session

    def get_by_id(self, media_id: str) -> Media | None:
        assert isinstance(self._session, Session)
        return self._session.get(Media, media_id)

    def create(self, media: Media) -> Media:
        assert isinstance(self._session, Session)
        self._session.add(media)
        self._session.flush()
        return media

    def delete(self, media: Media) -> None:
        assert isinstance(self._session, Session)
        self._session.delete(media)
        self._session.flush()

    async def get_by_id_async(self, media_id: str) -> Media | None:
        assert isinstance(self._session, AsyncSession)
        return await self._session.get(Media, media_id)

    async def create_async(self, media: Media) -> Media:
        assert isinstance(self._session, AsyncSession)
        self._session.add(media)
        await self._session.flush()
        return media

    async def delete_async(self, media: Media) -> None:
        assert isinstance(self._session, AsyncSession)
        await self._session.delete(media)
        await self._session.flush()

    async def list_for_owner_async(
        self, owner_id: str, *, offset: int = 0, limit: int = 50
    ) -> list[Media]:
        assert isinstance(self._session, AsyncSession)
        stmt = (
            select(Media)
            .where(Media.owner_id == owner_id)
            .order_by(Media.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return list(result.all())
