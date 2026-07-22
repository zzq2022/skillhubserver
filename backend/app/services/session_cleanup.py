"""Background cleanup of expired sessions (T10.3)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.database import get_async_session_factory

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 3600  # 1 hour


async def cleanup_expired_sessions_once() -> int:
    """Delete expired sessions; return count removed."""
    factory = get_async_session_factory()
    async with factory() as session:
        from app.repositories.session_repo import SessionRepository

        repo = SessionRepository(session)
        removed = await repo.cleanup_expired_async()
        await session.commit()
        return removed


async def session_cleanup_loop(
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run periodic session cleanup until stop_event is set."""
    stop = stop_event or asyncio.Event()
    while not stop.is_set():
        try:
            removed = await cleanup_expired_sessions_once()
            if removed:
                logger.info("session_cleanup removed %s expired session(s)", removed)
        except Exception:  # noqa: BLE001 — never crash the app loop
            logger.exception("session_cleanup failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue


def start_session_cleanup_task(
    *,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> tuple[asyncio.Task[Any], asyncio.Event]:
    """Spawn cleanup task; returns (task, stop_event)."""
    stop = asyncio.Event()
    task = asyncio.create_task(
        session_cleanup_loop(interval_seconds, stop),
        name="session-cleanup",
    )
    return task, stop
