"""User repository — CRUD and case-insensitive username lookup."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


class UserRepository:
    """Data access for the `users` table.

    Accepts either a sync `Session` or an async `AsyncSession`. Callers that
    use async must `await` the `*_async` methods; sync helpers keep the dual-DB
    fixtures simple.
    """

    def __init__(self, session: Session | AsyncSession) -> None:
        self._session = session

    # ---- sync API (tests / simple scripts) --------------------------------

    def get_by_id(self, user_id: str) -> User | None:
        assert isinstance(self._session, Session)
        return self._session.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        """Case-insensitive username lookup (stores original casing)."""
        assert isinstance(self._session, Session)
        stmt = select(User).where(func.lower(User.username) == username.lower())
        return self._session.scalars(stmt).first()

    def list_users(self, *, offset: int = 0, limit: int = 100) -> list[User]:
        assert isinstance(self._session, Session)
        stmt = select(User).order_by(User.created_at.asc()).offset(offset).limit(limit)
        return list(self._session.scalars(stmt).all())

    def count_users(self) -> int:
        assert isinstance(self._session, Session)
        return self._session.scalar(select(func.count()).select_from(User)) or 0

    def count_active_admins(self) -> int:
        assert isinstance(self._session, Session)
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        )
        return self._session.scalar(stmt) or 0

    def create(
        self,
        *,
        username: str,
        password_hash: str,
        role: UserRole = UserRole.USER,
        is_active: bool = True,
    ) -> User:
        assert isinstance(self._session, Session)
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
            is_active=is_active,
        )
        self._session.add(user)
        self._session.flush()
        return user

    def delete(self, user: User) -> None:
        assert isinstance(self._session, Session)
        self._session.delete(user)
        self._session.flush()

    # ---- async API (FastAPI request path) ---------------------------------

    async def get_by_id_async(self, user_id: str) -> User | None:
        assert isinstance(self._session, AsyncSession)
        return await self._session.get(User, user_id)

    async def get_by_username_async(self, username: str) -> User | None:
        assert isinstance(self._session, AsyncSession)
        stmt = select(User).where(func.lower(User.username) == username.lower())
        result = await self._session.scalars(stmt)
        return result.first()

    async def list_users_async(self, *, offset: int = 0, limit: int = 100) -> list[User]:
        assert isinstance(self._session, AsyncSession)
        stmt = select(User).order_by(User.created_at.asc()).offset(offset).limit(limit)
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def count_users_async(self) -> int:
        assert isinstance(self._session, AsyncSession)
        result = await self._session.scalar(select(func.count()).select_from(User))
        return result or 0

    async def count_active_admins_async(self) -> int:
        assert isinstance(self._session, AsyncSession)
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        )
        result = await self._session.scalar(stmt)
        return result or 0

    async def create_async(
        self,
        *,
        username: str,
        password_hash: str,
        role: UserRole = UserRole.USER,
        is_active: bool = True,
    ) -> User:
        assert isinstance(self._session, AsyncSession)
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
            is_active=is_active,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def delete_async(self, user: User) -> None:
        assert isinstance(self._session, AsyncSession)
        await self._session.delete(user)
        await self._session.flush()
