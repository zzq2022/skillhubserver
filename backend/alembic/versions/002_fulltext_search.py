"""Add full-text search: SQLite FTS5 virtual table or PG tsvector + GIN.

Revision ID: 002_fts
Revises: 001_initial
Create Date: 2026-07-22

Dialect-branched migration — each backend gets its native search structure.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_fts"
down_revision: Union[str, Sequence[str], None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        _upgrade_sqlite()
    elif dialect == "postgresql":
        _upgrade_postgresql()
    else:
        raise NotImplementedError(f"FTS migration not defined for dialect {dialect!r}")


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        _downgrade_sqlite()
    elif dialect == "postgresql":
        _downgrade_postgresql()
    else:
        raise NotImplementedError(f"FTS migration not defined for dialect {dialect!r}")


# ---------------------------------------------------------------------------
# SQLite FTS5
# ---------------------------------------------------------------------------

def _upgrade_sqlite() -> None:
    # skill_id UNINDEXED so we can join back to skills without indexing UUIDs.
    # tags stored as plain text (JSON string) for token matching.
    op.execute(
        """
        CREATE VIRTUAL TABLE skills_fts USING fts5(
            skill_id UNINDEXED,
            name,
            description,
            tags,
            tokenize = 'porter unicode61'
        )
        """
    )

    # Backfill existing rows
    op.execute(
        """
        INSERT INTO skills_fts(skill_id, name, description, tags)
        SELECT
            id,
            name,
            COALESCE(description, ''),
            COALESCE(tags, '[]')
        FROM skills
        """
    )

    # Keep FTS in sync with skills
    op.execute(
        """
        CREATE TRIGGER skills_fts_ai AFTER INSERT ON skills BEGIN
            INSERT INTO skills_fts(skill_id, name, description, tags)
            VALUES (
                new.id,
                new.name,
                COALESCE(new.description, ''),
                COALESCE(new.tags, '[]')
            );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER skills_fts_ad AFTER DELETE ON skills BEGIN
            DELETE FROM skills_fts WHERE skill_id = old.id;
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER skills_fts_au AFTER UPDATE ON skills BEGIN
            DELETE FROM skills_fts WHERE skill_id = old.id;
            INSERT INTO skills_fts(skill_id, name, description, tags)
            VALUES (
                new.id,
                new.name,
                COALESCE(new.description, ''),
                COALESCE(new.tags, '[]')
            );
        END
        """
    )


def _downgrade_sqlite() -> None:
    op.execute("DROP TRIGGER IF EXISTS skills_fts_au")
    op.execute("DROP TRIGGER IF EXISTS skills_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS skills_fts_ai")
    op.execute("DROP TABLE IF EXISTS skills_fts")


# ---------------------------------------------------------------------------
# PostgreSQL tsvector
# ---------------------------------------------------------------------------

def _upgrade_postgresql() -> None:
    op.add_column(
        "skills",
        sa.Column("search_vector", sa.dialects.postgresql.TSVECTOR(), nullable=True),
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION skills_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.tags::text, '')), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER skills_search_vector_trigger
        BEFORE INSERT OR UPDATE OF name, description, tags ON skills
        FOR EACH ROW
        EXECUTE PROCEDURE skills_search_vector_update()
        """
    )
    # Backfill
    op.execute(
        """
        UPDATE skills SET search_vector =
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(tags::text, '')), 'C')
        """
    )
    op.execute(
        "CREATE INDEX ix_skills_search_vector ON skills USING GIN (search_vector)"
    )


def _downgrade_postgresql() -> None:
    op.execute("DROP INDEX IF EXISTS ix_skills_search_vector")
    op.execute("DROP TRIGGER IF EXISTS skills_search_vector_trigger ON skills")
    op.execute("DROP FUNCTION IF EXISTS skills_search_vector_update")
    op.drop_column("skills", "search_vector")
