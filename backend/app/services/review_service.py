"""Publish review workflow: submit → approve / reject → unpublish."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.review import Review, ReviewStatus
from app.models.skill import PublishStatus, Skill, SkillVisibility
from app.models.user import User, UserRole
from app.repositories.review_repo import ReviewRepository
from app.repositories.skill_repo import SkillRepository
from app.services.auth_service import AuthError


class ReviewNotFound(AuthError):
    def __init__(self) -> None:
        super().__init__("review_not_found", "Review not found", 404)


class SkillNotFound(AuthError):
    def __init__(self) -> None:
        super().__init__("skill_not_found", "Skill not found", 404)


class SkillForbidden(AuthError):
    def __init__(self) -> None:
        super().__init__("skill_forbidden", "Not allowed to access this skill", 403)


class InvalidReviewState(AuthError):
    def __init__(self, message: str) -> None:
        super().__init__("invalid_review_state", message, 400)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReviewService:
    def __init__(self, session: Session | AsyncSession) -> None:
        self._session = session
        self._reviews = ReviewRepository(session)
        self._skills = SkillRepository(session)

    async def submit_async(self, skill_id: str, user: User) -> Review:
        """Owner submits skill for review: draft/rejected → pending_review."""
        skill = await self._skills.get_by_id_async(skill_id)
        if skill is None:
            raise SkillNotFound()
        if skill.owner_id != user.id and user.role != UserRole.ADMIN:
            raise SkillForbidden()

        if skill.publish_status == PublishStatus.PENDING_REVIEW:
            existing = await self._reviews.get_pending_for_skill_async(skill_id)
            if existing is not None:
                return existing
            raise InvalidReviewState("Skill is already pending review")

        if skill.publish_status == PublishStatus.PUBLISHED:
            raise InvalidReviewState("Skill is already published")

        # draft or rejected → pending
        pending = await self._reviews.get_pending_for_skill_async(skill_id)
        if pending is not None:
            raise InvalidReviewState("A pending review already exists")

        skill.publish_status = PublishStatus.PENDING_REVIEW
        # Stay private until approved
        skill.visibility = SkillVisibility.PRIVATE

        review = Review(
            skill_id=skill.id,
            submitter_id=user.id,
            status=ReviewStatus.PENDING,
        )
        await self._reviews.create_async(review)
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return review

    async def approve_async(self, review_id: str, admin: User) -> Review:
        review = await self._reviews.get_with_skill_async(review_id)
        if review is None:
            raise ReviewNotFound()
        if review.status != ReviewStatus.PENDING:
            raise InvalidReviewState("Review is not pending")

        skill = review.skill
        if skill is None:
            skill = await self._skills.get_by_id_async(review.skill_id)
        if skill is None:
            raise SkillNotFound()

        review.status = ReviewStatus.APPROVED
        review.reviewer_id = admin.id
        review.reviewed_at = _utcnow()
        skill.publish_status = PublishStatus.PUBLISHED
        skill.visibility = SkillVisibility.PUBLIC

        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return review

    async def reject_async(
        self, review_id: str, admin: User, *, comment: str | None = None
    ) -> Review:
        review = await self._reviews.get_with_skill_async(review_id)
        if review is None:
            raise ReviewNotFound()
        if review.status != ReviewStatus.PENDING:
            raise InvalidReviewState("Review is not pending")

        skill = review.skill or await self._skills.get_by_id_async(review.skill_id)
        if skill is None:
            raise SkillNotFound()

        review.status = ReviewStatus.REJECTED
        review.reviewer_id = admin.id
        review.reviewed_at = _utcnow()
        review.comment = comment
        skill.publish_status = PublishStatus.REJECTED
        skill.visibility = SkillVisibility.PRIVATE

        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return review

    async def unpublish_async(self, skill_id: str, admin: User) -> Skill:
        """Admin takes a public skill private again."""
        del admin  # auth enforced by route dependency
        skill = await self._skills.get_by_id_async(skill_id)
        if skill is None:
            raise SkillNotFound()
        is_public = (
            skill.visibility == SkillVisibility.PUBLIC
            and skill.publish_status == PublishStatus.PUBLISHED
        )
        if not is_public:
            raise InvalidReviewState("Skill is not public")

        skill.visibility = SkillVisibility.PRIVATE
        skill.publish_status = PublishStatus.DRAFT
        skill.featured = False
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
            await self._session.refresh(skill)
        return skill

    async def publish_async(self, skill_id: str, admin: User) -> Skill:
        """Admin force-publishes a skill to the public marketplace (no review gate)."""
        del admin
        skill = await self._skills.get_by_id_async(skill_id)
        if skill is None:
            raise SkillNotFound()
        if skill.publish_status == PublishStatus.PENDING_REVIEW:
            raise InvalidReviewState("Skill is pending review — approve or reject first")
        is_public = (
            skill.visibility == SkillVisibility.PUBLIC
            and skill.publish_status == PublishStatus.PUBLISHED
        )
        if is_public:
            raise InvalidReviewState("Skill is already public")

        skill.visibility = SkillVisibility.PUBLIC
        skill.publish_status = PublishStatus.PUBLISHED
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
            await self._session.refresh(skill)
        return skill

    async def list_pending_async(
        self, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[Review], int]:
        items = await self._reviews.list_pending_async(offset=offset, limit=limit)
        total = await self._reviews.count_pending_async()
        return items, total

    async def list_skills_async(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        q: str | None = None,
    ) -> tuple[list[Skill], int]:
        items = await self._skills.list_all_async(
            offset=offset, limit=limit, status=status, q=q
        )
        total = await self._skills.count_all_async(status=status, q=q)
        return items, total
