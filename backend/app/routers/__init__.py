"""FastAPI router modules."""

from app.routers import (
    admin,
    auth,
    bootstrap,
    compat_auth,
    compat_skillhub,
    import_export,
    media,
    skillhub,
    skills,
)

__all__ = [
    "admin",
    "auth",
    "bootstrap",
    "compat_auth",
    "compat_skillhub",
    "import_export",
    "media",
    "skillhub",
    "skills",
]
