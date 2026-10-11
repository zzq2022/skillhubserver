"""Client instance (device / installation) ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class ClientInstance(Base):
    __tablename__ = "client_instances"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    machine_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    os_platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    host_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    endpoint_url: Mapped[str | None] = mapped_column(String(256), nullable=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="online", server_default="online")
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    user = relationship("User", foreign_keys=[user_id])
    chat_sessions = relationship(
        "ClientChatSession",
        back_populates="client_instance",
        cascade="all, delete-orphan",
    )

    def is_online(self, threshold_seconds: int = 180) -> bool:
        """Returns True if the client has sent a heartbeat within threshold_seconds."""
        now = _utcnow()
        if not self.last_heartbeat_at:
            return False
        last_hb = self.last_heartbeat_at
        if last_hb.tzinfo is None:
            last_hb = last_hb.replace(tzinfo=timezone.utc)
        delta = (now - last_hb).total_seconds()
        return delta <= threshold_seconds

    def __repr__(self) -> str:
        return f"<ClientInstance id={self.id!r} machine={self.machine_name!r} status={self.status!r}>"
