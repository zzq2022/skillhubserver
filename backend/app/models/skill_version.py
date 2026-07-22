"""SkillVersion ORM model (linear snapshot history)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class SkillVersion(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "version_number", name="uq_skill_versions_skill_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    skill_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    skill = relationship("Skill", back_populates="versions")

    def __repr__(self) -> str:
        return (
            f"<SkillVersion id={self.id!r} skill_id={self.skill_id!r} "
            f"version_number={self.version_number}>"
        )
