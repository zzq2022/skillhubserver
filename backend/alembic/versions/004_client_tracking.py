"""Add client_instances and client_chat_sessions tables.

Revision ID: 004_client_tracking
Revises: 003_marketplace
Create Date: 2026-10-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_client_tracking"
down_revision: Union[str, Sequence[str], None] = "003_marketplace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_instances",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("machine_name", sa.String(length=128), nullable=True),
        sa.Column("os_platform", sa.String(length=64), nullable=True),
        sa.Column("app_version", sa.String(length=64), nullable=True),
        sa.Column("host_version", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="online", nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_client_instances_last_heartbeat_at", "client_instances", ["last_heartbeat_at"])
    op.create_index("ix_client_instances_user_id", "client_instances", ["user_id"])

    op.create_table(
        "client_chat_sessions",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("session_key", sa.String(length=128), nullable=False),
        sa.Column("client_instance_id", sa.String(length=64), sa.ForeignKey("client_instances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), server_default="未命名会话", nullable=False),
        sa.Column("workspace_name", sa.String(length=255), nullable=True),
        sa.Column("workspace_path", sa.String(length=512), nullable=True),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("message_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("session_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("messages_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_client_chat_sessions_session_key", "client_chat_sessions", ["session_key"])
    op.create_index("ix_client_chat_sessions_client_instance_id", "client_chat_sessions", ["client_instance_id"])
    op.create_index("ix_client_chat_sessions_user_id", "client_chat_sessions", ["user_id"])
    op.create_index("ix_client_chat_sessions_session_updated_at", "client_chat_sessions", ["session_updated_at"])


def downgrade() -> None:
    op.drop_table("client_chat_sessions")
    op.drop_table("client_instances")
