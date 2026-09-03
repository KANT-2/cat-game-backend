"""add task attempt grading result detail

Revision ID: d2a4c1b9e730
Revises: 4fc9c8f005f1
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2a4c1b9e730"
down_revision: str | Sequence[str] | None = "be8999b8f41e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("task_attempts", sa.Column("result_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("task_attempts", "result_detail")
