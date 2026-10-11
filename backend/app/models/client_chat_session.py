"""Client Chat Session ORM model for auditing conversation logs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class ClientChatSession(Base):
    __tablename__ = "client_chat_sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=_new_uuid)
    session_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    client_instance_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("client_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="未命名会话")
    workspace_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workspace_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    message_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    session_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    session_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    messages_json: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    client_instance = relationship("ClientInstance", back_populates="chat_sessions")
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<ClientChatSession id={self.id!r} title={self.title!r} client={self.client_instance_id!r}>"
