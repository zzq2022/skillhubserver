"""User management service (admin operations)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.review import Review, ReviewStatus
from app.models.skill import Skill, SkillVisibility
from app.models.user import User, UserRole
from app.repositories.session_repo import SessionRepository
from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthError, UsernameTaken
from app.utils.password import hash_password


class LastAdminProtected(AuthError):
    def __init__(self, action: str = "modify") -> None:
        super().__init__(
            "last_admin_protected",
            f"Cannot {action} the last active admin",
            400,
        )


class UserNotFound(AuthError):
    def __init__(self) -> None:
        super().__init__("user_not_found", "User not found", 404)


class UserService:
    """Admin-facing user lifecycle: create, role, enable/disable, delete."""

    def __init__(self, session: Session | AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._sessions = SessionRepository(session)

    # ---- async ------------------------------------------------------------

    async def list_users_async(self, *, offset: int = 0, limit: int = 100) -> list[User]:
        return await self._users.list_users_async(offset=offset, limit=limit)

    async def create_user_async(
        self,
        *,
        username: str,
        password: str,
        role: UserRole = UserRole.USER,
    ) -> User:
        existing = await self._users.get_by_username_async(username)
        if existing is not None:
            raise UsernameTaken()
        user = await self._users.create_async(
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return user

    async def set_role_async(self, user_id: str, role: UserRole) -> User:
        user = await self._users.get_by_id_async(user_id)
        if user is None:
            raise UserNotFound()
        if user.role == UserRole.ADMIN and role != UserRole.ADMIN:
            await self._ensure_not_last_admin_async(user)
        user.role = role
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return user

    async def set_active_async(self, user_id: str, is_active: bool) -> User:
        user = await self._users.get_by_id_async(user_id)
        if user is None:
            raise UserNotFound()
        if user.role == UserRole.ADMIN and user.is_active and not is_active:
            await self._ensure_not_last_admin_async(user)
        user.is_active = is_active
        if not is_active:
            # Immediate session invalidation for disabled users.
            await self._sessions.delete_for_user_async(user.id)
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return user

    async def delete_user_async(self, user_id: str) -> None:
        user = await self._users.get_by_id_async(user_id)
        if user is None:
            raise UserNotFound()
        if user.role == UserRole.ADMIN and user.is_active:
            await self._ensure_not_last_admin_async(user)
        await self._sessions.delete_for_user_async(user.id)
        await self._users.delete_async(user)
        if isinstance(self._session, AsyncSession):
            await self._session.commit()

    async def stats_async(self) -> dict[str, int]:
        assert isinstance(self._session, AsyncSession)
        users = await self._users.count_users_async()
        skills = await self._session.scalar(select(func.count()).select_from(Skill)) or 0
        public_skills = (
            await self._session.scalar(
                select(func.count())
                .select_from(Skill)
                .where(Skill.visibility == SkillVisibility.PUBLIC)
            )
            or 0
        )
        pending = (
            await self._session.scalar(
                select(func.count())
                .select_from(Review)
                .where(Review.status == ReviewStatus.PENDING)
            )
            or 0
        )
        from datetime import datetime, timezone, timedelta
        from app.models.client_chat_session import ClientChatSession
        from app.models.client_instance import ClientInstance

        online_threshold = datetime.now(timezone.utc) - timedelta(seconds=180)
        online_clients = (
            await self._session.scalar(
                select(func.count())
                .select_from(ClientInstance)
                .where(ClientInstance.last_heartbeat_at >= online_threshold)
            )
            or 0
        )
        total_clients = (
            await self._session.scalar(
                select(func.count()).select_from(ClientInstance)
            )
            or 0
        )
        chat_sessions = (
            await self._session.scalar(
                select(func.count()).select_from(ClientChatSession)
            )
            or 0
        )

        return {
            "users": users,
            "skills": skills,
            "public_skills": public_skills,
            "pending_reviews": pending,
            "online_clients": online_clients,
            "total_clients": total_clients,
            "chat_sessions": chat_sessions,
        }

    async def _ensure_not_last_admin_async(self, user: User) -> None:
        count = await self._users.count_active_admins_async()
        if count <= 1:
            raise LastAdminProtected()

    # ---- sync (tests) -----------------------------------------------------

    def create_user(
        self,
        *,
        username: str,
        password: str,
        role: UserRole = UserRole.USER,
    ) -> User:
        if self._users.get_by_username(username) is not None:
            raise UsernameTaken()
        user = self._users.create(
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        if isinstance(self._session, Session):
            self._session.commit()
        return user

    def set_role(self, user_id: str, role: UserRole) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFound()
        if user.role == UserRole.ADMIN and role != UserRole.ADMIN:
            self._ensure_not_last_admin(user)
        user.role = role
        if isinstance(self._session, Session):
            self._session.commit()
        return user

    def set_active(self, user_id: str, is_active: bool) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFound()
        if user.role == UserRole.ADMIN and user.is_active and not is_active:
            self._ensure_not_last_admin(user)
        user.is_active = is_active
        if not is_active:
            self._sessions.delete_for_user(user.id)
        if isinstance(self._session, Session):
            self._session.commit()
        return user

    def delete_user(self, user_id: str) -> None:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFound()
        if user.role == UserRole.ADMIN and user.is_active:
            self._ensure_not_last_admin(user)
        self._sessions.delete_for_user(user.id)
        self._users.delete(user)
        if isinstance(self._session, Session):
            self._session.commit()

    def _ensure_not_last_admin(self, user: User) -> None:
        if self._users.count_active_admins() <= 1:
            raise LastAdminProtected()
