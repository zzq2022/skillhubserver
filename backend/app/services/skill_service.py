"""Skill CRUD + version snapshots business logic."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.skill import PublishStatus, Skill, SkillVisibility
from app.models.skill_version import SkillVersion
from app.models.user import User, UserRole
from app.repositories.search import get_search_repository
from app.repositories.skill_repo import SkillRepository
from app.services.auth_service import AuthError
from app.services.skill_workspace import SkillWorkspace, WorkspaceError
from app.utils.skill_name import is_valid_skill_name, slugify, validate_skill_name


class SkillNotFound(AuthError):
    def __init__(self) -> None:
        super().__init__("skill_not_found", "Skill not found", 404)


class SkillForbidden(AuthError):
    def __init__(self) -> None:
        super().__init__("skill_forbidden", "Not allowed to access this skill", 403)


class SkillNameConflict(AuthError):
    def __init__(self) -> None:
        super().__init__(
            "skill_name_conflict",
            "A skill with this name already exists for the user",
            409,
        )


class InvalidSkillName(AuthError):
    def __init__(self, message: str) -> None:
        super().__init__("invalid_skill_name", message, 400)


class SkillService:
    def __init__(
        self,
        session: Session | AsyncSession,
        settings: Settings | None = None,
        workspace: SkillWorkspace | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._repo = SkillRepository(session)
        self._workspace = workspace or SkillWorkspace(self._settings)

    # ---- helpers ----------------------------------------------------------

    def _ensure_owner(self, skill: Skill, user: User) -> None:
        if skill.owner_id != user.id and user.role != UserRole.ADMIN:
            raise SkillForbidden()

    def _to_slug(self, name: str) -> str:
        try:
            if is_valid_skill_name(name):
                return validate_skill_name(name)
            return slugify(name)
        except ValueError as exc:
            raise InvalidSkillName(str(exc)) from exc

    # ---- async API --------------------------------------------------------

    async def list_skills_async(
        self,
        user: User,
        *,
        offset: int = 0,
        limit: int = 50,
        q: str | None = None,
    ) -> tuple[list[Skill], int]:
        # Full-text search path when a query is provided.
        if q and q.strip():
            search = get_search_repository(self._session, self._settings)
            # Fetch a window; total is the hit count within a generous cap.
            hits = await search.search_async(
                q,
                owner_id=user.id,
                limit=limit,
                offset=offset,
            )
            # For total, run without pagination (capped) — good enough for UX.
            all_hits = await search.search_async(
                q,
                owner_id=user.id,
                limit=1000,
                offset=0,
            )
            ids = [h.skill_id for h in hits]
            loaded = await self._repo.get_by_ids_async(ids)
            by_id = {s.id: s for s in loaded}
            skills = [by_id[i] for i in ids if i in by_id]
            return skills, len(all_hits)

        skills = await self._repo.list_for_owner_async(
            user.id, offset=offset, limit=limit, q=None
        )
        total = await self._repo.count_for_owner_async(user.id, q=None)
        return skills, total

    async def get_skill_async(self, skill_id: str, user: User) -> Skill:
        skill = await self._repo.get_by_id_async(skill_id)
        if skill is None:
            raise SkillNotFound()
        self._ensure_owner(skill, user)
        return skill

    async def create_skill_async(
        self,
        user: User,
        *,
        name: str,
        description: str | None = None,
        tags: list[str] | None = None,
        author: str | None = None,
        model: str | None = None,
        content: str | None = None,
    ) -> Skill:
        slug = self._to_slug(name)
        existing = await self._repo.get_by_owner_slug_async(user.id, slug)
        if existing is not None:
            raise SkillNameConflict()

        skill = Skill(
            owner_id=user.id,
            name=name if is_valid_skill_name(name) else slug,
            slug=slug,
            description=description,
            tags=list(tags or []),
            author=author,
            model=model,
            visibility=SkillVisibility.PRIVATE,
            publish_status=PublishStatus.DRAFT,
            version=1,
        )
        await self._repo.create_async(skill)

        try:
            self._workspace.create_package(
                slug=skill.slug,
                skill_id=skill.id,
                name=skill.name,
                description=skill.description,
                version=skill.version,
                tags=skill.tags,
                author=skill.author,
                model=skill.model,
                body=content or f"# {skill.name}\n",
            )
        except WorkspaceError as exc:
            raise AuthError("workspace_error", str(exc), 500) from exc

        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return skill

    async def update_skill_async(
        self,
        skill_id: str,
        user: User,
        *,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        author: str | None = None,
        model: str | None = None,
    ) -> Skill:
        skill = await self.get_skill_async(skill_id, user)
        old_slug = skill.slug

        if name is not None:
            new_slug = self._to_slug(name)
            if new_slug != skill.slug:
                conflict = await self._repo.get_by_owner_slug_async(user.id, new_slug)
                if conflict is not None and conflict.id != skill.id:
                    raise SkillNameConflict()
                skill.slug = new_slug
            skill.name = name if is_valid_skill_name(name) else new_slug

        if description is not None:
            skill.description = description
        if tags is not None:
            skill.tags = list(tags)
        if author is not None:
            skill.author = author
        if model is not None:
            skill.model = model

        # Rename package dir if slug changed
        if skill.slug != old_slug:
            old_pkg = self._workspace.package_dir(old_slug, skill.id)
            new_pkg = self._workspace.package_dir(skill.slug, skill.id)
            if old_pkg.is_dir() and not new_pkg.exists():
                old_pkg.rename(new_pkg)

        try:
            self._workspace.update_frontmatter(
                skill.slug,
                skill.id,
                name=skill.name,
                description=skill.description or "",
                version=skill.version,
                tags=skill.tags,
                author=skill.author or "",
                model=skill.model or "",
            )
        except WorkspaceError as exc:
            raise AuthError("workspace_error", str(exc), 500) from exc

        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return skill

    async def delete_skill_async(self, skill_id: str, user: User) -> None:
        skill = await self.get_skill_async(skill_id, user)
        slug, sid = skill.slug, skill.id
        await self._repo.delete_async(skill)
        self._workspace.delete_package(slug, sid)
        if isinstance(self._session, AsyncSession):
            await self._session.commit()

    async def get_content_async(self, skill_id: str, user: User) -> str:
        skill = await self.get_skill_async(skill_id, user)
        try:
            return self._workspace.read_skill_md(skill.slug, skill.id)
        except WorkspaceError as exc:
            raise AuthError("workspace_error", str(exc), 500) from exc

    async def update_content_async(
        self, skill_id: str, user: User, content: str
    ) -> str:
        skill = await self.get_skill_async(skill_id, user)
        try:
            self._workspace.write_skill_md(skill.slug, skill.id, content)
            # Pull sync keys from frontmatter into DB
            from app.services.skill_workspace import parse_skill_md

            meta, _ = parse_skill_md(content)
            if "description" in meta:
                skill.description = meta.get("description") or skill.description
            if "tags" in meta and isinstance(meta["tags"], list):
                skill.tags = meta["tags"]
            if "author" in meta:
                skill.author = meta.get("author") or skill.author
            if "model" in meta:
                skill.model = meta.get("model") or skill.model
            if "version" in meta:
                try:
                    skill.version = int(meta["version"])
                except (TypeError, ValueError):
                    pass
        except WorkspaceError as exc:
            raise AuthError("workspace_error", str(exc), 500) from exc

        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return content

    async def list_versions_async(
        self, skill_id: str, user: User
    ) -> list[SkillVersion]:
        await self.get_skill_async(skill_id, user)
        return await self._repo.list_versions_async(skill_id)

    async def create_version_async(
        self,
        skill_id: str,
        user: User,
        *,
        notes: str | None = None,
    ) -> SkillVersion:
        skill = await self.get_skill_async(skill_id, user)
        next_num = await self._repo.max_version_number_async(skill_id) + 1
        if next_num == 1:
            next_num = max(skill.version, 1)

        try:
            snapshot_path = self._workspace.create_version_snapshot(
                skill.slug, skill.id, next_num
            )
        except WorkspaceError as exc:
            raise AuthError("workspace_error", str(exc), 500) from exc

        version = SkillVersion(
            skill_id=skill.id,
            version_number=next_num,
            snapshot_path=snapshot_path,
            notes=notes,
        )
        await self._repo.create_version_async(version)
        skill.version = next_num
        try:
            self._workspace.update_frontmatter(
                skill.slug, skill.id, version=next_num
            )
        except WorkspaceError:
            pass

        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return version
