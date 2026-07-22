"""Marketplace discovery fields + skill_stars for AgentWork/Hope parity.

Revision ID: 003_marketplace
Revises: 002_fts
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_marketplace"
down_revision: Union[str, Sequence[str], None] = "002_fts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skills",
        sa.Column("category", sa.String(length=32), server_default="general", nullable=False),
    )
    op.add_column(
        "skills",
        sa.Column("download_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "skills",
        sa.Column("view_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "skills",
        sa.Column("star_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "skills",
        sa.Column("featured", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    )
    op.create_index("ix_skills_category", "skills", ["category"], unique=False)
    op.create_index("ix_skills_featured", "skills", ["featured"], unique=False)

    op.create_table(
        "skill_stars",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("skill_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "skill_id"),
    )
    op.create_index("ix_skill_stars_skill_id", "skill_stars", ["skill_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_skill_stars_skill_id", table_name="skill_stars")
    op.drop_table("skill_stars")
    op.drop_index("ix_skills_featured", table_name="skills")
    op.drop_index("ix_skills_category", table_name="skills")
    op.drop_column("skills", "featured")
    op.drop_column("skills", "star_count")
    op.drop_column("skills", "view_count")
    op.drop_column("skills", "download_count")
    op.drop_column("skills", "category")
