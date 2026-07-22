"""Review ORM model (skill publish review workflow)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    skill_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submitter_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(
            ReviewStatus,
            name="review_status",
            values_callable=lambda e: [m.value for m in e],
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=ReviewStatus.PENDING,
        server_default=ReviewStatus.PENDING.value,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    skill = relationship("Skill", back_populates="reviews")
    submitter = relationship("User", foreign_keys=[submitter_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])

    def __repr__(self) -> str:
        return f"<Review id={self.id!r} skill_id={self.skill_id!r} status={self.status!r}>"
