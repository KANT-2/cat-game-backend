"""add Part 2 task classification and multiple-choice metadata

Revision ID: a31f20c72b11
Revises: d2a4c1b9e730
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a31f20c72b11"
down_revision: str | Sequence[str] | None = "d2a4c1b9e730"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks", sa.Column("domain", sa.String(), server_default="PYTHON", nullable=False)
    )
    op.add_column("tasks", sa.Column("options", postgresql.JSONB(), nullable=True))
    op.add_column("tasks", sa.Column("correct_option", sa.String(), nullable=True))
    op.execute("UPDATE tasks SET type = 'CODE' WHERE type NOT IN ('CODE', 'MULTIPLE_CHOICE')")
    op.execute("UPDATE tasks SET difficulty = upper(difficulty)")
    op.execute(
        "UPDATE tasks SET difficulty = 'BRONZE' WHERE difficulty NOT IN ('BRONZE', 'SILVER', 'GOLD')"
    )
    op.create_check_constraint("ck_tasks_type", "tasks", "type IN ('CODE', 'MULTIPLE_CHOICE')")
    op.create_check_constraint("ck_tasks_domain", "tasks", "domain IN ('PYTHON', 'SQL')")
    op.create_check_constraint(
        "ck_tasks_difficulty", "tasks", "difficulty IN ('BRONZE', 'SILVER', 'GOLD')"
    )
    op.create_check_constraint(
        "ck_tasks_grading_metadata",
        "tasks",
        "(type = 'CODE' AND options IS NULL AND correct_option IS NULL) OR "
        "(type = 'MULTIPLE_CHOICE' AND options IS NOT NULL AND correct_option IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tasks_grading_metadata", "tasks", type_="check")
    op.drop_constraint("ck_tasks_difficulty", "tasks", type_="check")
    op.drop_constraint("ck_tasks_domain", "tasks", type_="check")
    op.drop_constraint("ck_tasks_type", "tasks", type_="check")
    op.drop_column("tasks", "correct_option")
    op.drop_column("tasks", "options")
    op.drop_column("tasks", "domain")
