"""Public SkillHub catalog endpoints (no auth)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.schemas.review import HubSkillOut
from app.services.hub_service import HubService
from app.services.skill_workspace import SkillWorkspace

router = APIRouter(prefix="/hub", tags=["skillhub"])


def _hub_skill_out(skill, owner_username: str) -> dict[str, Any]:  # noqa: ANN001
    return HubSkillOut(
        id=skill.id,
        name=skill.name,
        slug=skill.slug,
        description=skill.description,
        tags=list(skill.tags or []),
        author=skill.author,
        model=skill.model,
        version=skill.version,
        owner=owner_username,
        updated_at=skill.updated_at.isoformat() if skill.updated_at else "",
    ).model_dump(by_alias=True)


@router.get("/skills")
async def list_public_skills(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None),
) -> dict:
    service = HubService(db, settings)
    skills, total = await service.list_public_async(offset=offset, limit=limit, q=q)

    # Resolve owner usernames in batch
    owner_ids = {s.owner_id for s in skills}
    from app.models.user import User

    owners: dict[str, str] = {}
    for oid in owner_ids:
        u = await db.get(User, oid)
        if u:
            owners[oid] = u.username

    return {
        "data": [_hub_skill_out(s, owners.get(s.owner_id, "")) for s in skills],
        "pagination": {
            "page": (offset // limit) + 1 if limit else 1,
            "pageSize": limit,
            "total": total,
        },
    }


@router.get("/skills/{owner}/{name}")
async def get_public_skill(
    owner: str,
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    service = HubService(db, settings)
    skill, user = await service.get_public_async(owner, name)
    return {"data": _hub_skill_out(skill, user.username)}


@router.get("/skills/{owner}/{name}/download")
async def download_public_skill(
    owner: str,
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Download skill package as ZIP (Phase 7 will fully harden packaging)."""
    import io
    import zipfile

    from fastapi.responses import StreamingResponse

    service = HubService(db, settings)
    skill, user = await service.get_public_async(owner, name)
    workspace = SkillWorkspace(settings)
    pkg = workspace.package_dir(skill.slug, skill.id)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if pkg.is_dir():
            for path in pkg.rglob("*"):
                if path.is_file():
                    arcname = path.relative_to(pkg).as_posix()
                    zf.write(path, arcname)
        else:
            # Fallback: only SKILL.md content if workspace missing
            try:
                content = workspace.read_skill_md(skill.slug, skill.id)
            except Exception:
                content = f"# {skill.name}\n"
            zf.writestr("SKILL.md", content)

    buf.seek(0)
    filename = f"{user.username}-{skill.slug}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
