"""AgentWork-compatible SkillHub operations for Hope clients."""

from __future__ import annotations

import base64
import io
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.skill import SKILL_CATEGORIES, PublishStatus, Skill, SkillVisibility
from app.models.skill_star import SkillStar
from app.models.user import User
from app.repositories.skill_repo import SkillRepository
from app.services.auth_service import AuthError
from app.services.hub_service import HubService
from app.services.import_export_service import ImportExportService, ImportError_
from app.services.review_service import ReviewService
from app.services.skill_service import SkillService
from app.services.skill_workspace import SkillWorkspace, WorkspaceError


class CompatNotFound(AuthError):
    def __init__(self, message: str = "Skill not found") -> None:
        super().__init__("skill_not_found", message, 404)


class CompatForbidden(AuthError):
    def __init__(self, message: str = "Not allowed") -> None:
        super().__init__("forbidden", message, 403)


def _aw_visibility(skill: Skill) -> str:
    """Map internal visibility/status to AgentWork 'private'|'shared'."""
    if skill.visibility == SkillVisibility.PUBLIC and skill.publish_status == PublishStatus.PUBLISHED:
        return "shared"
    return "private"


def _aw_approval(skill: Skill) -> str | None:
    """Map publish_status to AgentWork approvalStatus."""
    mapping = {
        PublishStatus.PUBLISHED: "approved",
        PublishStatus.PENDING_REVIEW: "pending",
        PublishStatus.REJECTED: "rejected",
        PublishStatus.DRAFT: None,
    }
    return mapping.get(skill.publish_status)


def _registry_slug(owner_username: str, skill: Skill) -> str:
    return f"{owner_username}/{skill.slug}"


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    try:
        # Hope's custom deserializer accepts RFC3339 strings; include Z for UTC.
        if getattr(dt, "tzinfo", None) is None:
            return dt.isoformat() + "Z"
        return dt.isoformat()
    except Exception:
        return str(dt)


# Hope UI category chips are Chinese labels; map to our enum keys.
_HOPE_CATEGORY_ALIASES: dict[str, str] = {
    "全部": "all",
    "通用": "general",
    "办公工具": "office",
    "开发工具": "dev",
    "AI 生成": "ai",
    "AI生成": "ai",
    "数据分析": "data",
    "项目管理": "management",
    "部署": "deploy",
    "设计": "design",
    "安全": "security",
    "元技能": "meta",
}


def normalize_category(category: str | None) -> str | None:
    """Map Hope Chinese labels (and common aliases) to internal category keys."""
    if category is None:
        return None
    raw = category.strip()
    if not raw or raw == "all":
        return None
    mapped = _HOPE_CATEGORY_ALIASES.get(raw, raw)
    if mapped == "all":
        return None
    if mapped in SKILL_CATEGORIES:
        return mapped
    # Unknown category → no results (don't 500); treat as empty filter match
    return mapped


class CompatSkillHubService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        workspace: SkillWorkspace | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._skills = SkillRepository(session)
        self._workspace = workspace or SkillWorkspace(self._settings)
        self._hub = HubService(session, self._settings)
        self._import_export = ImportExportService(session, self._settings, self._workspace)
        self._reviews = ReviewService(session)

    # ---- private list (Hope sync) ------------------------------------------

    async def list_private(self, user: User) -> list[dict[str, Any]]:
        skills = await self._skills.list_for_owner_async(user.id, offset=0, limit=500)
        out: list[dict[str, Any]] = []
        for s in skills:
            out.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description or "",
                    "visibility": _aw_visibility(s),
                    "slug": s.slug,
                    "registrySlug": _registry_slug(user.username, s),
                    "approvalStatus": _aw_approval(s),
                    "ownerUserId": s.owner_id,
                    "userId": s.owner_id,
                    "category": s.category,
                    "starCount": s.star_count,
                    "downloadCount": s.download_count,
                    "viewCount": s.view_count,
                    "updatedAt": _iso(s.updated_at),
                }
            )
        return out

    # ---- public catalog ----------------------------------------------------

    async def browse_public(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        sort: str | None = None,
        category: str | None = None,
        q: str | None = None,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        offset = (page - 1) * page_size

        # Base: public skills
        category = normalize_category(category)

        if q and q.strip():
            skills, total = await self._hub.list_public_async(
                offset=offset, limit=page_size, q=q.strip()
            )
        else:
            skills, total = await self._list_public_sorted(
                offset=offset,
                limit=page_size,
                sort=sort or "new",
                category=category,
            )

        starred: set[str] = set()
        if actor_id and skills:
            starred = await self._starred_ids(actor_id, [s.id for s in skills])

        owner_ids = {s.owner_id for s in skills}
        owners = await self._load_usernames(owner_ids)

        items = [
            self._public_summary(s, owners.get(s.owner_id, ""), is_starred=s.id in starred)
            for s in skills
        ]
        return {
            "items": items,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "startIndex": offset if total else 0,
            "endIndex": offset + len(items) - 1 if items else -1,
        }

    async def _list_public_sorted(
        self,
        *,
        offset: int,
        limit: int,
        sort: str,
        category: str | None,
    ) -> tuple[list[Skill], int]:
        stmt = select(Skill).where(
            Skill.visibility == SkillVisibility.PUBLIC,
            Skill.publish_status == PublishStatus.PUBLISHED,
        )
        count_stmt = (
            select(func.count())
            .select_from(Skill)
            .where(
                Skill.visibility == SkillVisibility.PUBLIC,
                Skill.publish_status == PublishStatus.PUBLISHED,
            )
        )
        if category and category != "all":
            stmt = stmt.where(Skill.category == category)
            count_stmt = count_stmt.where(Skill.category == category)

        if sort == "top":
            stmt = stmt.order_by(Skill.download_count.desc(), Skill.updated_at.desc())
        elif sort == "most_starred":
            stmt = stmt.order_by(Skill.star_count.desc(), Skill.updated_at.desc())
        elif sort == "featured":
            stmt = stmt.where(Skill.featured.is_(True)).order_by(Skill.updated_at.desc())
            count_stmt = count_stmt.where(Skill.featured.is_(True))
        elif sort == "trending":
            # Simple stand-in: recent engagement proxy (downloads + stars + views)
            stmt = stmt.order_by(
                (Skill.download_count + Skill.star_count + Skill.view_count).desc(),
                Skill.updated_at.desc(),
            )
        else:  # new
            stmt = stmt.order_by(Skill.updated_at.desc())

        total = int(await self._session.scalar(count_stmt) or 0)
        result = await self._session.scalars(stmt.offset(offset).limit(limit))
        return list(result.all()), total

    def _public_summary(
        self, skill: Skill, owner_username: str, *, is_starred: bool = False
    ) -> dict[str, Any]:
        desc = skill.description or ""
        if len(desc) > 500:
            desc = desc[:500]
        # Hope SkillHubPublicSkill uses serde aliases:
        #   registrySlug alias slug, downloads alias downloadCount, etc.
        # Sending BOTH primary + alias keys makes serde fail decode (duplicate field).
        # Prefer AgentWork wire names that Hope accepts via alias; single key each.
        # One key per Hope field — aliases would collide if both present.
        # Hope: registrySlug (alias slug), downloads (alias downloadCount),
        # stars (alias starCount), views (alias viewCount),
        # authorUsername (alias authorName).
        return {
            "id": skill.id,
            "name": skill.name,
            "description": desc,
            "registrySlug": _registry_slug(owner_username, skill),
            "authorName": owner_username,
            "category": skill.category,
            "downloadCount": int(skill.download_count or 0),
            "starCount": int(skill.star_count or 0),
            "viewCount": int(skill.view_count or 0),
            "updatedAt": _iso(skill.updated_at),
            "isStarred": is_starred,
            "featured": bool(skill.featured),
        }

    async def get_public_detail(
        self, skill_id: str, actor_id: str | None = None
    ) -> dict[str, Any]:
        skill = await self._skills.get_by_id_async(skill_id)
        if skill is None:
            raise CompatNotFound()
        is_public = (
            skill.visibility == SkillVisibility.PUBLIC
            and skill.publish_status == PublishStatus.PUBLISHED
        )
        if not is_public and (actor_id is None or skill.owner_id != actor_id):
            raise CompatNotFound()

        owner = await self._session.get(User, skill.owner_id)
        owner_name = owner.username if owner else ""
        skill_md: str | None = None
        skill_md_available = False
        try:
            skill_md = self._workspace.read_skill_md(skill.slug, skill.id)
            skill_md_available = True
        except WorkspaceError:
            skill_md = None
            skill_md_available = False

        is_starred = False
        if actor_id:
            is_starred = skill_id in await self._starred_ids(actor_id, [skill_id])

        return {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description or "",
            "visibility": _aw_visibility(skill),
            "ownerUserId": skill.owner_id,
            "skillMd": skill_md,
            "skillMdAvailable": skill_md_available,
            # SkillDetail.slug is plain Option (no alias) — short slug is fine.
            "slug": skill.slug,
            "approvalStatus": _aw_approval(skill),
            "authorName": owner_name,
            "category": skill.category,
            "starCount": int(skill.star_count or 0),
            "downloadCount": int(skill.download_count or 0),
            "viewCount": int(skill.view_count or 0),
            "isStarred": is_starred,
            "featured": bool(skill.featured),
        }

    async def get_private_detail(self, user: User, skill_id: str) -> dict[str, Any]:
        skill = await self._skills.get_by_id_async(skill_id)
        if skill is None or skill.owner_id != user.id:
            raise CompatNotFound()
        return await self.get_public_detail(skill_id, actor_id=user.id)

    # ---- stars / views / downloads -----------------------------------------

    async def toggle_star(self, user: User, skill_id: str) -> dict[str, bool]:
        skill = await self._skills.get_by_id_async(skill_id)
        if skill is None:
            raise CompatNotFound()
        if skill.visibility != SkillVisibility.PUBLIC:
            raise CompatNotFound("Only public skills can be starred")

        existing = await self._session.get(SkillStar, (user.id, skill_id))

        if existing is not None:
            await self._session.delete(existing)
            skill.star_count = max(0, (skill.star_count or 0) - 1)
            await self._session.commit()
            return {"starred": False}

        self._session.add(SkillStar(user_id=user.id, skill_id=skill_id))
        skill.star_count = (skill.star_count or 0) + 1
        await self._session.commit()
        return {"starred": True}

    async def increment_view(self, skill_id: str) -> None:
        skill = await self._skills.get_by_id_async(skill_id)
        if skill is None:
            return
        skill.view_count = (skill.view_count or 0) + 1
        await self._session.commit()

    async def download_zip(
        self, skill_id: str, actor: User | None
    ) -> tuple[bytes, str]:
        skill = await self._skills.get_by_id_async(skill_id)
        if skill is None:
            raise CompatNotFound()
        is_public = (
            skill.visibility == SkillVisibility.PUBLIC
            and skill.publish_status == PublishStatus.PUBLISHED
        )
        is_owner = actor is not None and skill.owner_id == actor.id
        if not is_public and not is_owner:
            raise CompatNotFound()

        data = self._import_export.export_zip_bytes(skill)
        if is_public:
            skill.download_count = (skill.download_count or 0) + 1
            await self._session.commit()
        return data, f"{skill.slug}.zip"

    async def marketplace_stats(self) -> dict[str, int]:
        total_skills = int(
            await self._session.scalar(
                select(func.count())
                .select_from(Skill)
                .where(
                    Skill.visibility == SkillVisibility.PUBLIC,
                    Skill.publish_status == PublishStatus.PUBLISHED,
                )
            )
            or 0
        )
        total_stars = int(
            await self._session.scalar(
                select(func.coalesce(func.sum(Skill.star_count), 0)).where(
                    Skill.visibility == SkillVisibility.PUBLIC,
                    Skill.publish_status == PublishStatus.PUBLISHED,
                )
            )
            or 0
        )
        total_downloads = int(
            await self._session.scalar(
                select(func.coalesce(func.sum(Skill.download_count), 0)).where(
                    Skill.visibility == SkillVisibility.PUBLIC,
                    Skill.publish_status == PublishStatus.PUBLISHED,
                )
            )
            or 0
        )
        return {
            "totalSkills": total_skills,
            "totalStars": total_stars,
            "totalDownloads": total_downloads,
        }

    async def featured_skills(self, limit: int = 6) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 50)
        stmt = (
            select(Skill)
            .where(
                Skill.visibility == SkillVisibility.PUBLIC,
                Skill.publish_status == PublishStatus.PUBLISHED,
                Skill.featured.is_(True),
            )
            .order_by(Skill.updated_at.desc())
            .limit(limit)
        )
        skills = list((await self._session.scalars(stmt)).all())
        owners = await self._load_usernames({s.owner_id for s in skills})
        return [
            self._public_summary(s, owners.get(s.owner_id, "")) for s in skills
        ]

    # ---- review submission (Hope package upload) ---------------------------

    async def submit_review_package(
        self,
        user: User,
        *,
        file_name: str,
        package_base64: str,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        author: str | None = None,
    ) -> dict[str, Any]:
        try:
            raw = base64.b64decode(package_base64, validate=False)
        except Exception as exc:
            raise AuthError("invalid_package", "packageBase64 is not valid base64", 400) from exc

        try:
            skill = await self._import_export.import_async(
                user,
                io.BytesIO(raw),
                filename=file_name or "skill.zip",
            )
        except ImportError_ as exc:
            raise exc

        # Optional metadata overrides from Hope
        if name:
            skill.name = name.strip()[:100]
        if description is not None:
            skill.description = description
        if tags is not None:
            skill.tags = list(tags)
        if author:
            skill.author = author[:100]
        if category and category in SKILL_CATEGORIES:
            skill.category = category

        await self._session.commit()

        review = await self._reviews.submit_async(skill.id, user)
        # reload skill after status change
        skill = await self._skills.get_by_id_async(skill.id)
        assert skill is not None

        return {
            "id": skill.id,
            "skillId": skill.id,
            "name": skill.name,
            "slug": skill.slug,
            "registrySlug": _registry_slug(user.username, skill),
            "visibility": _aw_visibility(skill),
            "approvalStatus": _aw_approval(skill),
            "ownerUserId": skill.owner_id,
            "userId": skill.owner_id,
            "reviewId": review.id,
        }

    async def delete_skill(self, user: User, skill_id: str) -> dict[str, bool]:
        service = SkillService(self._session, self._settings, self._workspace)
        await service.delete_skill_async(skill_id, user)
        return {"ok": True}

    # ---- helpers -----------------------------------------------------------

    async def _load_usernames(self, owner_ids: set[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for oid in owner_ids:
            u = await self._session.get(User, oid)
            if u:
                out[oid] = u.username
        return out

    async def _starred_ids(self, user_id: str, skill_ids: list[str]) -> set[str]:
        if not skill_ids:
            return set()
        stmt = select(SkillStar.skill_id).where(
            SkillStar.user_id == user_id,
            SkillStar.skill_id.in_(skill_ids),
        )
        result = await self._session.scalars(stmt)
        return set(result.all())
