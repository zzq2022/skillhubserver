"""Media upload / fetch / delete with type & size validation."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.media import Media
from app.models.user import User, UserRole
from app.repositories.media_repo import MediaRepository
from app.services.auth_service import AuthError

ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/svg+xml",
    }
)

EXT_BY_TYPE: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}

# Strip path components and unsafe chars from client filename (display only)
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class MediaNotFound(AuthError):
    def __init__(self) -> None:
        super().__init__("media_not_found", "Media not found", 404)


class MediaForbidden(AuthError):
    def __init__(self) -> None:
        super().__init__("media_forbidden", "Not allowed to access this media", 403)


class MediaValidationError(AuthError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 400)


def sanitize_filename(name: str | None) -> str:
    """Return a basename-only safe display filename (never used for storage path)."""
    if not name:
        return "upload"
    # Drop any directory components (path traversal in original name)
    base = Path(name.replace("\\", "/")).name
    base = SAFE_FILENAME_RE.sub("_", base).strip("._") or "upload"
    return base[:200]


class MediaService:
    def __init__(
        self,
        session: Session | AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._repo = MediaRepository(session)
        self._media_root = Path(self._settings.DATA_ROOT) / "media"
        self._media_root.mkdir(parents=True, exist_ok=True)
        self._max_size = self._settings.MAX_UPLOAD_SIZE

    def _absolute_path(self, storage_path: str) -> Path:
        """Resolve storage_path under media root; reject escape."""
        # storage_path is relative like "2026/07/<uuid>.png"
        root = self._media_root.resolve()
        candidate = (self._media_root / storage_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise MediaValidationError(
                "invalid_storage_path", "Invalid media storage path"
            ) from exc
        return candidate

    def _ensure_owner(self, media: Media, user: User) -> None:
        if media.owner_id != user.id and user.role != UserRole.ADMIN:
            raise MediaForbidden()

    async def upload_async(
        self,
        user: User,
        file_obj: BinaryIO,
        *,
        filename: str | None,
        content_type: str | None,
        size_hint: int | None = None,
    ) -> Media:
        ctype = (content_type or "").split(";")[0].strip().lower()
        if ctype not in ALLOWED_CONTENT_TYPES:
            raise MediaValidationError(
                "unsupported_media_type",
                f"Content type not allowed: {ctype or 'unknown'}",
            )

        if size_hint is not None and size_hint > self._max_size:
            raise MediaValidationError(
                "file_too_large",
                f"File exceeds maximum size of {self._max_size} bytes",
            )

        # Stream with hard cap
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = file_obj.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > self._max_size:
                raise MediaValidationError(
                    "file_too_large",
                    f"File exceeds maximum size of {self._max_size} bytes",
                )
            chunks.append(chunk)
        data = b"".join(chunks)
        if not data:
            raise MediaValidationError("empty_file", "Uploaded file is empty")

        display_name = sanitize_filename(filename)
        ext = EXT_BY_TYPE[ctype]
        now = datetime.now(timezone.utc)
        rel_dir = f"{now.year:04d}/{now.month:02d}"
        file_id = str(uuid.uuid4())
        storage_path = f"{rel_dir}/{file_id}{ext}"

        abs_path = self._absolute_path(storage_path)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(data)

        if display_name.lower().endswith(ext):
            final_name = display_name
        elif "." not in display_name:
            final_name = display_name + ext
        else:
            final_name = Path(display_name).stem + ext

        media = Media(
            owner_id=user.id,
            filename=final_name,
            content_type=ctype,
            size_bytes=len(data),
            storage_path=storage_path,
        )

        await self._repo.create_async(media)
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return media

    async def get_async(self, media_id: str, user: User) -> Media:
        media = await self._repo.get_by_id_async(media_id)
        if media is None:
            raise MediaNotFound()
        self._ensure_owner(media, user)
        return media

    async def read_bytes_async(self, media_id: str, user: User) -> tuple[Media, bytes]:
        media = await self.get_async(media_id, user)
        path = self._absolute_path(media.storage_path)
        if not path.is_file():
            raise MediaNotFound()
        return media, path.read_bytes()

    async def delete_async(self, media_id: str, user: User) -> None:
        media = await self.get_async(media_id, user)
        path = self._absolute_path(media.storage_path)
        await self._repo.delete_async(media)
        if path.is_file():
            path.unlink()
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
