"""Review repository — publish workflow records."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.models.review import Review, ReviewStatus
from app.models.skill import Skill


class ReviewRepository:
    def __init__(self, session: Session | AsyncSession) -> None:
        self._session = session

    # ---- sync -------------------------------------------------------------

    def get_by_id(self, review_id: str) -> Review | None:
        assert isinstance(self._session, Session)
        return self._session.get(Review, review_id)

    def get_with_skill(self, review_id: str) -> Review | None:
        assert isinstance(self._session, Session)
        stmt = (
            select(Review)
            .where(Review.id == review_id)
            .options(selectinload(Review.skill))
        )
        return self._session.scalars(stmt).first()

    def list_pending(self, *, offset: int = 0, limit: int = 50) -> list[Review]:
        assert isinstance(self._session, Session)
        stmt = (
            select(Review)
            .where(Review.status == ReviewStatus.PENDING)
            .options(selectinload(Review.skill))
            .order_by(Review.submitted_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_pending_for_skill(self, skill_id: str) -> Review | None:
        assert isinstance(self._session, Session)
        stmt = select(Review).where(
            Review.skill_id == skill_id,
            Review.status == ReviewStatus.PENDING,
        )
        return self._session.scalars(stmt).first()

    def create(self, review: Review) -> Review:
        assert isinstance(self._session, Session)
        self._session.add(review)
        self._session.flush()
        return review

    # ---- async ------------------------------------------------------------

    async def get_by_id_async(self, review_id: str) -> Review | None:
        assert isinstance(self._session, AsyncSession)
        return await self._session.get(Review, review_id)

    async def get_with_skill_async(self, review_id: str) -> Review | None:
        assert isinstance(self._session, AsyncSession)
        stmt = (
            select(Review)
            .where(Review.id == review_id)
            .options(selectinload(Review.skill))
        )
        result = await self._session.scalars(stmt)
        return result.first()

    async def list_pending_async(
        self, *, offset: int = 0, limit: int = 50
    ) -> list[Review]:
        assert isinstance(self._session, AsyncSession)
        stmt = (
            select(Review)
            .where(Review.status == ReviewStatus.PENDING)
            .options(selectinload(Review.skill))
            .order_by(Review.submitted_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def count_pending_async(self) -> int:
        assert isinstance(self._session, AsyncSession)
        result = await self._session.scalar(
            select(func.count())
            .select_from(Review)
            .where(Review.status == ReviewStatus.PENDING)
        )
        return result or 0

    async def get_pending_for_skill_async(self, skill_id: str) -> Review | None:
        assert isinstance(self._session, AsyncSession)
        stmt = select(Review).where(
            Review.skill_id == skill_id,
            Review.status == ReviewStatus.PENDING,
        )
        result = await self._session.scalars(stmt)
        return result.first()

    async def create_async(self, review: Review) -> Review:
        assert isinstance(self._session, AsyncSession)
        self._session.add(review)
        await self._session.flush()
        return review

    # ---- public catalog helpers -------------------------------------------

    async def list_public_skills_async(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        skill_ids: list[str] | None = None,
    ) -> list[Skill]:
        """List public+published skills (optionally constrained to ids)."""
        assert isinstance(self._session, AsyncSession)
        from app.models.skill import PublishStatus, SkillVisibility

        stmt = select(Skill).where(
            Skill.visibility == SkillVisibility.PUBLIC,
            Skill.publish_status == PublishStatus.PUBLISHED,
        )
        if skill_ids is not None:
            if not skill_ids:
                return []
            stmt = stmt.where(Skill.id.in_(skill_ids))
        stmt = stmt.order_by(Skill.updated_at.desc()).offset(offset).limit(limit)
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def count_public_skills_async(self) -> int:
        assert isinstance(self._session, AsyncSession)
        from app.models.skill import PublishStatus, SkillVisibility

        result = await self._session.scalar(
            select(func.count())
            .select_from(Skill)
            .where(
                Skill.visibility == SkillVisibility.PUBLIC,
                Skill.publish_status == PublishStatus.PUBLISHED,
            )
        )
        return result or 0

    async def get_public_by_owner_name_async(
        self, owner_username: str, name: str
    ) -> Skill | None:
        assert isinstance(self._session, AsyncSession)
        from app.models.skill import PublishStatus, SkillVisibility
        from app.models.user import User

        stmt = (
            select(Skill)
            .join(User, User.id == Skill.owner_id)
            .where(
                func.lower(User.username) == owner_username.lower(),
                Skill.slug == name,
                Skill.visibility == SkillVisibility.PUBLIC,
                Skill.publish_status == PublishStatus.PUBLISHED,
            )
        )
        result = await self._session.scalars(stmt)
        return result.first()
