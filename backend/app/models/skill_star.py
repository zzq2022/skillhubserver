"""Per-user star/favorite on a published skill."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SkillStar(Base):
    __tablename__ = "skill_stars"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    skill_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    skill = relationship("Skill", back_populates="stars")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<SkillStar user_id={self.user_id!r} skill_id={self.skill_id!r}>"
