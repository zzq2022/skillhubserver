"""Initial schema: users, sessions, skills, skill_versions, reviews, media.

Revision ID: 001_initial
Revises:
Create Date: 2026-07-22

Compatible with both SQLite and PostgreSQL. Enums are stored as VARCHAR with
CHECK constraints (native_enum=False) so the same migration applies to both
dialects without dialect-specific DDL branches.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- users ----
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "user", name="user_role", native_enum=False, length=20),
            server_default="user",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=False)

    # ---- sessions ----
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)

    # ---- skills ----
    op.create_table(
        "skills",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "visibility",
            sa.Enum(
                "private",
                "public",
                name="skill_visibility",
                native_enum=False,
                length=20,
            ),
            server_default="private",
            nullable=False,
        ),
        sa.Column(
            "publish_status",
            sa.Enum(
                "draft",
                "pending_review",
                "published",
                "rejected",
                name="publish_status",
                native_enum=False,
                length=32,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("tags", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("author", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "slug", name="uq_skills_owner_slug"),
    )
    op.create_index("ix_skills_owner_id", "skills", ["owner_id"], unique=False)

    # ---- skill_versions ----
    op.create_table(
        "skill_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("skill_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot_path", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "skill_id", "version_number", name="uq_skill_versions_skill_number"
        ),
    )
    op.create_index(
        "ix_skill_versions_skill_id", "skill_versions", ["skill_id"], unique=False
    )

    # ---- reviews ----
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("skill_id", sa.String(length=36), nullable=False),
        sa.Column("submitter_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                name="review_status",
                native_enum=False,
                length=20,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitter_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reviews_skill_id", "reviews", ["skill_id"], unique=False)
    op.create_index("ix_reviews_submitter_id", "reviews", ["submitter_id"], unique=False)
    op.create_index("ix_reviews_reviewer_id", "reviews", ["reviewer_id"], unique=False)

    # ---- media ----
    op.create_table(
        "media",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_owner_id", "media", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_media_owner_id", table_name="media")
    op.drop_table("media")

    op.drop_index("ix_reviews_reviewer_id", table_name="reviews")
    op.drop_index("ix_reviews_submitter_id", table_name="reviews")
    op.drop_index("ix_reviews_skill_id", table_name="reviews")
    op.drop_table("reviews")

    op.drop_index("ix_skill_versions_skill_id", table_name="skill_versions")
    op.drop_table("skill_versions")

    op.drop_index("ix_skills_owner_id", table_name="skills")
    op.drop_table("skills")

    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
