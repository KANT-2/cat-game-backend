"""make concepts the authoritative task domain

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Move the domain classification from each task to its concept."""
    op.add_column("concepts", sa.Column("domain", sa.String(), nullable=True))
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM tasks
                GROUP BY concept_id
                HAVING COUNT(DISTINCT domain) > 1
            ) THEN
                RAISE EXCEPTION 'a concept is linked to tasks from multiple domains';
            END IF;
        END $$
        """
    )
    op.execute(
        """
        UPDATE concepts AS c
        SET domain = CASE
            WHEN c.name LIKE 'SQL:%' THEN 'SQL'
            WHEN c.name LIKE 'PYTHON:%' THEN 'PYTHON'
            ELSE COALESCE(
                (SELECT MIN(t.domain) FROM tasks AS t WHERE t.concept_id = c.id),
                'PYTHON'
            )
        END
        """
    )
    op.alter_column("concepts", "domain", nullable=False)
    op.create_check_constraint(
        "ck_concepts_domain",
        "concepts",
        "domain IN ('PYTHON', 'SQL')",
    )
    op.drop_constraint("concepts_name_key", "concepts", type_="unique")
    op.execute(
        "UPDATE concepts SET name = regexp_replace(name, '^(PYTHON|SQL):', '')"
    )
    op.create_unique_constraint(
        "uq_concepts_domain_name",
        "concepts",
        ["domain", "name"],
    )
    op.drop_constraint("ck_tasks_domain", "tasks", type_="check")
    op.drop_column("tasks", "domain")


def downgrade() -> None:
    """Restore the denormalized task domain and prefixed concept names."""
    op.add_column("tasks", sa.Column("domain", sa.String(), nullable=True))
    op.execute(
        """
        UPDATE tasks AS t
        SET domain = c.domain
        FROM concepts AS c
        WHERE c.id = t.concept_id
        """
    )
    op.alter_column(
        "tasks",
        "domain",
        nullable=False,
        server_default="PYTHON",
    )
    op.create_check_constraint(
        "ck_tasks_domain",
        "tasks",
        "domain IN ('PYTHON', 'SQL')",
    )
    op.drop_constraint("uq_concepts_domain_name", "concepts", type_="unique")
    op.execute("UPDATE concepts SET name = domain || ':' || name")
    op.create_unique_constraint("concepts_name_key", "concepts", ["name"])
    op.drop_constraint("ck_concepts_domain", "concepts", type_="check")
    op.drop_column("concepts", "domain")
