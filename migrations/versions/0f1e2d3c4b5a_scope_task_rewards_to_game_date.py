"""scope task rewards to one grant per game date

Revision ID: 0f1e2d3c4b5a
Revises: f2a3b4c5d6e7
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0f1e2d3c4b5a"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow one reward ledger row per user, task and Asia/Seoul game date."""
    op.add_column("task_completions", sa.Column("completion_date", sa.Date(), nullable=True))
    op.execute(
        "UPDATE task_completions "
        "SET completion_date = (completed_at AT TIME ZONE 'Asia/Seoul')::date"
    )
    op.alter_column("task_completions", "completion_date", nullable=False)
    op.drop_constraint("uq_task_completions_user_task", "task_completions", type_="unique")
    op.create_unique_constraint(
        "uq_task_completions_user_task_date",
        "task_completions",
        ["user_id", "task_id", "completion_date"],
    )


def downgrade() -> None:
    """Restore lifetime uniqueness, retaining the earliest reward row per task."""
    op.drop_constraint(
        "uq_task_completions_user_task_date",
        "task_completions",
        type_="unique",
    )
    op.execute(
        "DELETE FROM task_completions current_row USING task_completions earlier_row "
        "WHERE current_row.user_id = earlier_row.user_id "
        "AND current_row.task_id = earlier_row.task_id "
        "AND (current_row.completed_at, current_row.id) > "
        "(earlier_row.completed_at, earlier_row.id)"
    )
    op.drop_column("task_completions", "completion_date")
    op.create_unique_constraint(
        "uq_task_completions_user_task",
        "task_completions",
        ["user_id", "task_id"],
    )
