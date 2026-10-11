"""SQLAlchemy ORM models.

Importing this package registers every model on `Base.metadata` so Alembic
autogenerate and `Base.metadata.create_all` see the full schema.
"""

from app.models.client_chat_session import ClientChatSession
from app.models.client_instance import ClientInstance
from app.models.media import Media
from app.models.review import Review, ReviewStatus
from app.models.session import Session
from app.models.skill import PublishStatus, Skill, SkillVisibility
from app.models.skill_star import SkillStar
from app.models.skill_version import SkillVersion
from app.models.user import User, UserRole

__all__ = [
    "ClientChatSession",
    "ClientInstance",
    "Media",
    "PublishStatus",
    "Review",
    "ReviewStatus",
    "Session",
    "Skill",
    "SkillStar",
    "SkillVersion",
    "SkillVisibility",
    "User",
    "UserRole",
]
