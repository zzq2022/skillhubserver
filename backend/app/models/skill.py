"""Skill ORM model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Fixed Hub filter enum (AgentWork / Hope parity)
SKILL_CATEGORIES = frozenset(
    {
        "general",
        "office",
        "dev",
        "ai",
        "data",
        "management",
        "deploy",
        "design",
        "security",
        "meta",
    }
)


class SkillVisibility(str, enum.Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class PublishStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="uq_skills_owner_slug"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[SkillVisibility] = mapped_column(
        Enum(
            SkillVisibility,
            name="skill_visibility",
            values_callable=lambda e: [m.value for m in e],
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=SkillVisibility.PRIVATE,
        server_default=SkillVisibility.PRIVATE.value,
    )
    publish_status: Mapped[PublishStatus] = mapped_column(
        Enum(
            PublishStatus,
            name="publish_status",
            values_callable=lambda e: [m.value for m in e],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=PublishStatus.DRAFT,
        server_default=PublishStatus.DRAFT.value,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    tags: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="general",
        server_default="general",
        index=True,
    )
    download_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    star_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    featured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", index=True
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

    owner = relationship("User", back_populates="skills")
    versions = relationship(
        "SkillVersion",
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="SkillVersion.version_number",
    )
    reviews = relationship("Review", back_populates="skill", cascade="all, delete-orphan")
    stars = relationship(
        "SkillStar",
        back_populates="skill",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Skill id={self.id!r} slug={self.slug!r} owner_id={self.owner_id!r}>"
