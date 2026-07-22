"""Skill + skill_versions data access."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.models.skill import PublishStatus, Skill, SkillVisibility
from app.models.skill_version import SkillVersion


class SkillRepository:
    def __init__(self, session: Session | AsyncSession) -> None:
        self._session = session

    # ---- sync -------------------------------------------------------------

    def get_by_id(self, skill_id: str) -> Skill | None:
        assert isinstance(self._session, Session)
        return self._session.get(Skill, skill_id)

    def get_by_owner_slug(self, owner_id: str, slug: str) -> Skill | None:
        assert isinstance(self._session, Session)
        stmt = select(Skill).where(Skill.owner_id == owner_id, Skill.slug == slug)
        return self._session.scalars(stmt).first()

    def list_for_owner(
        self,
        owner_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
        q: str | None = None,
    ) -> list[Skill]:
        assert isinstance(self._session, Session)
        stmt = select(Skill).where(Skill.owner_id == owner_id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                (Skill.name.ilike(like)) | (Skill.description.ilike(like))
            )
        stmt = stmt.order_by(Skill.updated_at.desc()).offset(offset).limit(limit)
        return list(self._session.scalars(stmt).all())

    def count_for_owner(self, owner_id: str, *, q: str | None = None) -> int:
        assert isinstance(self._session, Session)
        stmt = select(func.count()).select_from(Skill).where(Skill.owner_id == owner_id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                (Skill.name.ilike(like)) | (Skill.description.ilike(like))
            )
        return self._session.scalar(stmt) or 0

    def create(self, skill: Skill) -> Skill:
        assert isinstance(self._session, Session)
        self._session.add(skill)
        self._session.flush()
        return skill

    def delete(self, skill: Skill) -> None:
        assert isinstance(self._session, Session)
        self._session.delete(skill)
        self._session.flush()

    def list_versions(self, skill_id: str) -> list[SkillVersion]:
        assert isinstance(self._session, Session)
        stmt = (
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill_id)
            .order_by(SkillVersion.version_number.desc())
        )
        return list(self._session.scalars(stmt).all())

    def create_version(self, version: SkillVersion) -> SkillVersion:
        assert isinstance(self._session, Session)
        self._session.add(version)
        self._session.flush()
        return version

    # ---- async ------------------------------------------------------------

    async def get_by_id_async(self, skill_id: str) -> Skill | None:
        assert isinstance(self._session, AsyncSession)
        return await self._session.get(Skill, skill_id)

    async def get_by_owner_slug_async(self, owner_id: str, slug: str) -> Skill | None:
        assert isinstance(self._session, AsyncSession)
        stmt = select(Skill).where(Skill.owner_id == owner_id, Skill.slug == slug)
        result = await self._session.scalars(stmt)
        return result.first()

    async def list_for_owner_async(
        self,
        owner_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
        q: str | None = None,
    ) -> list[Skill]:
        assert isinstance(self._session, AsyncSession)
        stmt = select(Skill).where(Skill.owner_id == owner_id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                (Skill.name.ilike(like)) | (Skill.description.ilike(like))
            )
        stmt = stmt.order_by(Skill.updated_at.desc()).offset(offset).limit(limit)
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def count_for_owner_async(
        self, owner_id: str, *, q: str | None = None
    ) -> int:
        assert isinstance(self._session, AsyncSession)
        stmt = select(func.count()).select_from(Skill).where(Skill.owner_id == owner_id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                (Skill.name.ilike(like)) | (Skill.description.ilike(like))
            )
        result = await self._session.scalar(stmt)
        return result or 0

    async def create_async(self, skill: Skill) -> Skill:
        assert isinstance(self._session, AsyncSession)
        self._session.add(skill)
        await self._session.flush()
        return skill

    async def delete_async(self, skill: Skill) -> None:
        assert isinstance(self._session, AsyncSession)
        await self._session.delete(skill)
        await self._session.flush()

    async def list_versions_async(self, skill_id: str) -> list[SkillVersion]:
        assert isinstance(self._session, AsyncSession)
        stmt = (
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill_id)
            .order_by(SkillVersion.version_number.desc())
        )
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def create_version_async(self, version: SkillVersion) -> SkillVersion:
        assert isinstance(self._session, AsyncSession)
        self._session.add(version)
        await self._session.flush()
        return version

    async def max_version_number_async(self, skill_id: str) -> int:
        assert isinstance(self._session, AsyncSession)
        result = await self._session.scalar(
            select(func.max(SkillVersion.version_number)).where(
                SkillVersion.skill_id == skill_id
            )
        )
        return int(result or 0)

    def get_by_ids(self, skill_ids: list[str]) -> list[Skill]:
        """Load skills by id (order not preserved)."""
        assert isinstance(self._session, Session)
        if not skill_ids:
            return []
        stmt = select(Skill).where(Skill.id.in_(skill_ids))
        return list(self._session.scalars(stmt).all())

    async def get_by_ids_async(self, skill_ids: list[str]) -> list[Skill]:
        assert isinstance(self._session, AsyncSession)
        if not skill_ids:
            return []
        stmt = select(Skill).where(Skill.id.in_(skill_ids))
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def list_all_async(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        q: str | None = None,
    ) -> list[Skill]:
        """Admin catalog: all skills, optional status filter (public|private|pending|draft)."""
        assert isinstance(self._session, AsyncSession)
        stmt = select(Skill)
        stmt = self._apply_admin_filters(stmt, status=status, q=q)
        stmt = stmt.order_by(Skill.updated_at.desc()).offset(offset).limit(limit)
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def count_all_async(
        self,
        *,
        status: str | None = None,
        q: str | None = None,
    ) -> int:
        assert isinstance(self._session, AsyncSession)
        stmt = select(func.count()).select_from(Skill)
        stmt = self._apply_admin_filters(stmt, status=status, q=q)
        return int(await self._session.scalar(stmt) or 0)

    @staticmethod
    def _apply_admin_filters(stmt, *, status: str | None, q: str | None):  # noqa: ANN001
        if status == "public":
            # On marketplace
            stmt = stmt.where(
                Skill.visibility == SkillVisibility.PUBLIC,
                Skill.publish_status == PublishStatus.PUBLISHED,
            )
        elif status in ("unpublished", "private"):
            # Not on marketplace (draft / pending / rejected / private)
            stmt = stmt.where(
                (Skill.visibility != SkillVisibility.PUBLIC)
                | (Skill.publish_status != PublishStatus.PUBLISHED)
            )
        elif status == "pending":
            stmt = stmt.where(Skill.publish_status == PublishStatus.PENDING_REVIEW)
        elif status == "draft":
            stmt = stmt.where(Skill.publish_status == PublishStatus.DRAFT)
        elif status == "rejected":
            stmt = stmt.where(Skill.publish_status == PublishStatus.REJECTED)
        if q and q.strip():
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                (Skill.name.ilike(like)) | (Skill.description.ilike(like))
            )
        return stmt
