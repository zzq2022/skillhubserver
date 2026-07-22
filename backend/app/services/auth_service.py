"""Authentication service: login, logout, current user, change password."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole
from app.repositories.session_repo import SessionRepository
from app.repositories.user_repo import UserRepository
from app.utils.password import hash_password, needs_rehash, verify_password


class AuthError(Exception):
    """Base class for auth failures that map to HTTP responses."""

    def __init__(self, code: str, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class InvalidCredentials(AuthError):
    def __init__(self) -> None:
        super().__init__("invalid_credentials", "Invalid username or password", 401)


class UserDisabled(AuthError):
    def __init__(self) -> None:
        super().__init__("user_disabled", "User account is disabled", 403)


class NotAuthenticated(AuthError):
    def __init__(self) -> None:
        super().__init__("not_authenticated", "Authentication required", 401)


class SessionExpired(AuthError):
    def __init__(self) -> None:
        super().__init__("session_expired", "Session has expired", 401)


class WrongPassword(AuthError):
    def __init__(self) -> None:
        super().__init__("wrong_password", "Current password is incorrect", 400)


class AlreadyInitialized(AuthError):
    def __init__(self) -> None:
        super().__init__(
            "already_initialized",
            "Instance is already initialized",
            409,
        )


class UsernameTaken(AuthError):
    def __init__(self) -> None:
        super().__init__("username_taken", "Username is already taken", 409)


@dataclass(frozen=True)
class AuthResult:
    user: User
    session: SessionModel
    csrf_token: str
    session_id: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_token(nbytes: int = 32) -> str:
    """Return a URL-safe random token (64 hex chars for nbytes=32)."""
    return secrets.token_hex(nbytes)


class AuthService:
    """Business rules for authentication and session lifecycle."""

    def __init__(
        self,
        session: Session | AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._users = UserRepository(session)
        self._sessions = SessionRepository(session)

    # ---- async (FastAPI) --------------------------------------------------

    async def login_async(self, username: str, password: str) -> AuthResult:
        user = await self._users.get_by_username_async(username)
        if user is None or not verify_password(user.password_hash, password):
            raise InvalidCredentials()
        if not user.is_active:
            raise UserDisabled()

        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        return await self._create_session_async(user)

    async def logout_async(self, session_id: str) -> None:
        await self._sessions.delete_async(session_id)
        if isinstance(self._session, AsyncSession):
            await self._session.commit()

    async def get_current_user_async(self, session_id: str | None) -> tuple[User, SessionModel]:
        if not session_id:
            raise NotAuthenticated()

        row = await self._sessions.get_with_user_async(session_id)
        if row is None:
            raise NotAuthenticated()

        now = _utcnow()
        if self._is_expired(row, now):
            await self._sessions.delete_async(session_id)
            if isinstance(self._session, AsyncSession):
                await self._session.commit()
            raise SessionExpired()

        user = row.user
        if user is None or not user.is_active:
            await self._sessions.delete_async(session_id)
            if isinstance(self._session, AsyncSession):
                await self._session.commit()
            raise UserDisabled() if user and not user.is_active else NotAuthenticated()

        await self._sessions.touch_async(row, now)
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return user, row

    async def change_password_async(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        if not verify_password(user.password_hash, current_password):
            raise WrongPassword()
        user.password_hash = hash_password(new_password)
        # Revoke other sessions so stolen cookies die after password change.
        await self._sessions.delete_for_user_async(user.id)
        if isinstance(self._session, AsyncSession):
            await self._session.commit()

    async def bootstrap_status_async(self) -> tuple[bool, bool]:
        count = await self._users.count_users_async()
        initialized = count > 0
        return initialized, initialized  # registrationClosed == initialized

    async def bootstrap_init_async(self, username: str, password: str) -> AuthResult:
        count = await self._users.count_users_async()
        if count > 0:
            raise AlreadyInitialized()

        existing = await self._users.get_by_username_async(username)
        if existing is not None:
            raise UsernameTaken()

        user = await self._users.create_async(
            username=username,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return await self._create_session_async(user)

    async def _create_session_async(self, user: User) -> AuthResult:
        now = _utcnow()
        session_id = _new_token(32)
        csrf_token = _new_token(32)
        expires_at = now + timedelta(seconds=self._settings.SESSION_MAX_AGE)
        row = await self._sessions.create_async(
            session_id=session_id,
            user_id=user.id,
            csrf_token=csrf_token,
            expires_at=expires_at,
            last_active_at=now,
        )
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return AuthResult(user=user, session=row, csrf_token=csrf_token, session_id=session_id)

    # ---- sync (tests) -----------------------------------------------------

    def login(self, username: str, password: str) -> AuthResult:
        user = self._users.get_by_username(username)
        if user is None or not verify_password(user.password_hash, password):
            raise InvalidCredentials()
        if not user.is_active:
            raise UserDisabled()
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        return self._create_session(user)

    def logout(self, session_id: str) -> None:
        self._sessions.delete(session_id)
        if isinstance(self._session, Session):
            self._session.commit()

    def get_current_user(self, session_id: str | None) -> tuple[User, SessionModel]:
        if not session_id:
            raise NotAuthenticated()
        row = self._sessions.get_with_user(session_id)
        if row is None:
            raise NotAuthenticated()
        now = _utcnow()
        if self._is_expired(row, now):
            self._sessions.delete(session_id)
            if isinstance(self._session, Session):
                self._session.commit()
            raise SessionExpired()
        user = row.user
        if user is None or not user.is_active:
            self._sessions.delete(session_id)
            if isinstance(self._session, Session):
                self._session.commit()
            raise UserDisabled() if user and not user.is_active else NotAuthenticated()
        self._sessions.touch(row, now)
        if isinstance(self._session, Session):
            self._session.commit()
        return user, row

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(user.password_hash, current_password):
            raise WrongPassword()
        user.password_hash = hash_password(new_password)
        self._sessions.delete_for_user(user.id)
        if isinstance(self._session, Session):
            self._session.commit()

    def bootstrap_init(self, username: str, password: str) -> AuthResult:
        if self._users.count_users() > 0:
            raise AlreadyInitialized()
        if self._users.get_by_username(username) is not None:
            raise UsernameTaken()
        user = self._users.create(
            username=username,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        if isinstance(self._session, Session):
            self._session.commit()
        return self._create_session(user)

    def _create_session(self, user: User) -> AuthResult:
        now = _utcnow()
        session_id = _new_token(32)
        csrf_token = _new_token(32)
        expires_at = now + timedelta(seconds=self._settings.SESSION_MAX_AGE)
        row = self._sessions.create(
            session_id=session_id,
            user_id=user.id,
            csrf_token=csrf_token,
            expires_at=expires_at,
            last_active_at=now,
        )
        if isinstance(self._session, Session):
            self._session.commit()
        return AuthResult(user=user, session=row, csrf_token=csrf_token, session_id=session_id)

    def _is_expired(self, row: SessionModel, now: datetime) -> bool:
        """Absolute expiry OR idle timeout exceeded."""
        expires_at = row.expires_at
        last_active = row.last_active_at
        # Normalize naive datetimes (SQLite may drop tzinfo).
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)

        if expires_at < now:
            return True
        idle = now - last_active
        if idle.total_seconds() > self._settings.SESSION_IDLE_TIMEOUT:
            return True
        return False
