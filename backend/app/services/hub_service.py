"""Public SkillHub catalog (no auth required for list/detail/download)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.skill import Skill
from app.models.user import User
from app.repositories.review_repo import ReviewRepository
from app.repositories.search import get_search_repository
from app.repositories.skill_repo import SkillRepository
from app.services.auth_service import AuthError


class HubNotFound(AuthError):
    def __init__(self) -> None:
        super().__init__("hub_skill_not_found", "Public skill not found", 404)


class HubService:
    def __init__(
        self,
        session: Session | AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._reviews = ReviewRepository(session)
        self._skills = SkillRepository(session)

    async def list_public_async(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        q: str | None = None,
    ) -> tuple[list[Skill], int]:
        if q and q.strip():
            search = get_search_repository(self._session, self._settings)
            hits = await search.search_async(
                q,
                visibility="public",
                limit=limit,
                offset=offset,
            )
            all_hits = await search.search_async(
                q,
                visibility="public",
                limit=1000,
                offset=0,
            )
            ids = [h.skill_id for h in hits]
            skills = await self._reviews.list_public_skills_async(skill_ids=ids)
            by_id = {s.id: s for s in skills}
            ordered = [by_id[i] for i in ids if i in by_id]
            return ordered, len(all_hits)

        skills = await self._reviews.list_public_skills_async(
            offset=offset, limit=limit
        )
        total = await self._reviews.count_public_skills_async()
        return skills, total

    async def get_public_async(self, owner: str, name: str) -> tuple[Skill, User]:
        skill = await self._reviews.get_public_by_owner_name_async(owner, name)
        if skill is None:
            raise HubNotFound()
        user = await self._session.get(User, skill.owner_id)  # type: ignore[union-attr]
        if user is None:
            raise HubNotFound()
        return skill, user
