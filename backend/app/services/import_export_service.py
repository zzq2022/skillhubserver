"""ZIP import / export for skill packages.

Security (T7.1):
- Zip-slip: reject absolute paths and any member that would escape extract root
- Reject symlink / hardlink members
- Enforce max archive size and max uncompressed size
- Require SKILL.md at package root (or single top-level folder)
"""

from __future__ import annotations

import io
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.skill import PublishStatus, Skill, SkillVisibility
from app.models.user import User
from app.repositories.skill_repo import SkillRepository
from app.services.auth_service import AuthError
from app.services.skill_workspace import (
    SkillWorkspace,
    WorkspaceError,
    parse_skill_md,
)
from app.utils.skill_name import is_valid_skill_name, slugify, validate_skill_name

# Defaults when Settings has no dedicated ZIP fields
DEFAULT_MAX_ZIP_BYTES = 50 * 1024 * 1024  # 50 MB compressed
DEFAULT_MAX_UNCOMPRESSED = 100 * 1024 * 1024  # 100 MB expanded
DEFAULT_MAX_FILES = 500


class ImportError_(AuthError):
    """Import/export domain error (named to avoid shadowing builtins.ImportError)."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(code, message, status_code)


class ImportExportService:
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
        self._max_zip = getattr(
            self._settings, "MAX_ZIP_SIZE", DEFAULT_MAX_ZIP_BYTES
        )
        self._max_uncompressed = getattr(
            self._settings, "MAX_ZIP_UNCOMPRESSED", DEFAULT_MAX_UNCOMPRESSED
        )
        self._max_files = getattr(
            self._settings, "MAX_ZIP_FILES", DEFAULT_MAX_FILES
        )

    # ---- export -----------------------------------------------------------

    def export_zip_bytes(self, skill: Skill) -> bytes:
        """Pack skill workspace into a ZIP (in-memory)."""
        pkg = self._workspace.package_dir(skill.slug, skill.id)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if pkg.is_dir():
                for path in sorted(pkg.rglob("*")):
                    if not path.is_file():
                        continue
                    # Skip nested version snapshots for export? Include full package.
                    if path.is_symlink():
                        continue
                    arcname = path.relative_to(pkg).as_posix()
                    zf.write(path, arcname)
            else:
                try:
                    content = self._workspace.read_skill_md(skill.slug, skill.id)
                except WorkspaceError:
                    content = f"# {skill.name}\n"
                zf.writestr("SKILL.md", content)
        return buf.getvalue()

    async def export_async(self, skill_id: str, user: User) -> tuple[bytes, str]:
        from app.services.skill_service import SkillService

        skill = await SkillService(
            self._session, self._settings, self._workspace
        ).get_skill_async(skill_id, user)
        data = self.export_zip_bytes(skill)
        filename = f"{skill.slug}.zip"
        return data, filename

    # ---- import -----------------------------------------------------------

    async def import_async(
        self,
        user: User,
        file_obj: BinaryIO,
        *,
        filename: str | None = None,
        size_hint: int | None = None,
    ) -> Skill:
        """Validate and import a skill ZIP into a new private draft skill."""
        raw = file_obj.read()
        if size_hint is not None and size_hint > self._max_zip:
            raise ImportError_("zip_too_large", "ZIP file exceeds size limit")
        if len(raw) > self._max_zip:
            raise ImportError_("zip_too_large", "ZIP file exceeds size limit")
        if len(raw) == 0:
            raise ImportError_("zip_empty", "ZIP file is empty")

        extract_root = Path(tempfile.mkdtemp(prefix="skillhub-import-"))
        try:
            self._safe_extract(raw, extract_root)
            package_root = self._find_package_root(extract_root)
            skill_md = package_root / "SKILL.md"
            if not skill_md.is_file():
                raise ImportError_(
                    "missing_skill_md",
                    "ZIP must contain SKILL.md at package root",
                )

            content = skill_md.read_text(encoding="utf-8")
            meta, body = parse_skill_md(content)
            name = meta.get("name") or (Path(filename or "imported").stem)
            if not isinstance(name, str) or not name.strip():
                name = "imported-skill"
            name = str(name).strip()

            try:
                if is_valid_skill_name(name):
                    slug = validate_skill_name(name)
                else:
                    slug = slugify(name)
            except ValueError as exc:
                raise ImportError_("invalid_skill_name", str(exc)) from exc

            existing = await self._repo.get_by_slug_any_owner_async(slug)
            if existing is not None:
                raise ImportError_(
                    "skill_exists",
                    f"该技能名称「{slug}」已存在，只有管理员才能下架或删除原有技能后再行提交。",
                    409,
                )

            description = meta.get("description")
            if description is not None:
                description = str(description)
            tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
            author = str(meta["author"]) if meta.get("author") else None
            model = str(meta["model"]) if meta.get("model") else None
            version = 1
            if meta.get("version") is not None:
                try:
                    version = int(meta["version"])
                except (TypeError, ValueError):
                    version = 1

            skill = Skill(
                owner_id=user.id,
                name=name if is_valid_skill_name(name) else slug,
                slug=slug,
                description=description,
                tags=list(tags),
                author=author,
                model=model,
                visibility=SkillVisibility.PRIVATE,
                publish_status=PublishStatus.DRAFT,
                version=version,
            )
            await self._repo.create_async(skill)

            dest = self._workspace.package_dir(skill.slug, skill.id)
            if dest.exists():
                raise ImportError_("workspace_error", "Package directory exists", 500)
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Copy extracted package into final location
            shutil.copytree(package_root, dest)
            # Ensure SKILL.md has consistent content on disk
            try:
                self._workspace.write_skill_md(skill.slug, skill.id, content)
            except WorkspaceError:
                # If write fails because structure odd, leave copied files
                pass
            (dest / "versions").mkdir(exist_ok=True)
            (dest / "assets").mkdir(exist_ok=True)

            if isinstance(self._session, AsyncSession):
                await self._session.commit()
            return skill
        finally:
            shutil.rmtree(extract_root, ignore_errors=True)

    # ---- zip safety -------------------------------------------------------

    def _safe_extract(self, raw: bytes, dest: Path) -> None:
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as exc:
            raise ImportError_("invalid_zip", "Corrupted or invalid ZIP file") from exc

        with zf:
            infos = zf.infolist()
            if len(infos) > self._max_files:
                raise ImportError_(
                    "zip_too_many_files",
                    f"ZIP contains more than {self._max_files} entries",
                )

            total_uncompressed = 0
            for info in infos:
                self._validate_member(info)
                total_uncompressed += info.file_size
                if total_uncompressed > self._max_uncompressed:
                    raise ImportError_(
                        "zip_uncompressed_too_large",
                        "Uncompressed ZIP content exceeds size limit",
                    )

            dest_resolved = dest.resolve()
            for info in infos:
                # Directory entries
                target = self._member_target(dest, info.filename)
                if not self._is_within(dest_resolved, target):
                    raise ImportError_(
                        "zip_slip",
                        f"Illegal path in ZIP: {info.filename!r}",
                    )
                if info.is_dir() or info.filename.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)

    def _validate_member(self, info: zipfile.ZipInfo) -> None:
        name = info.filename
        if not name or name.strip() == "":
            raise ImportError_("zip_invalid_entry", "ZIP contains empty entry name")

        # Absolute paths / drive letters
        if name.startswith(("/", "\\")) or (len(name) > 1 and name[1] == ":"):
            raise ImportError_("zip_slip", f"Absolute path in ZIP: {name!r}")

        # Symlink / hardlink via external attributes (Unix)
        # Upper 16 bits of external_attr are Unix mode when create_system == 3
        if info.create_system == 3:  # Unix
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise ImportError_(
                    "zip_symlink",
                    f"Symbolic links are not allowed: {name!r}",
                )

        # Also reject if filename itself is a link marker some tools use
        parts = Path(name.replace("\\", "/")).parts
        if ".." in parts:
            raise ImportError_("zip_slip", f"Path traversal in ZIP: {name!r}")

    def _member_target(self, dest: Path, filename: str) -> Path:
        # Normalize separators; never allow absolute
        normalized = filename.replace("\\", "/").lstrip("/")
        return (dest / normalized).resolve()

    @staticmethod
    def _is_within(root: Path, candidate: Path) -> bool:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False

    def _find_package_root(self, extract_root: Path) -> Path:
        """If ZIP has a single top-level dir, use it; else extract_root."""
        if (extract_root / "SKILL.md").is_file():
            return extract_root
        children = [p for p in extract_root.iterdir() if not p.name.startswith(".")]
        dirs = [p for p in children if p.is_dir()]
        files = [p for p in children if p.is_file()]
        if len(dirs) == 1 and not files:
            inner = dirs[0]
            if (inner / "SKILL.md").is_file():
                return inner
        # Fallback: search one level for SKILL.md
        for p in extract_root.rglob("SKILL.md"):
            if p.is_file():
                return p.parent
        return extract_root
