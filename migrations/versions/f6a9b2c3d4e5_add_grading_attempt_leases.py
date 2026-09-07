"""add durable grading attempt leases

Revision ID: f6a9b2c3d4e5
Revises: e5f8a1b2c3d4
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a9b2c3d4e5"
down_revision: str | Sequence[str] | None = "e5f8a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add an expiring opaque lease used by dedicated grading workers."""
    op.add_column(
        "task_attempts",
        sa.Column("grading_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "task_attempts",
        sa.Column("grading_lease_token", sa.UUID(), nullable=True),
    )
    op.create_index(
        "ix_task_attempts_grading_queue",
        "task_attempts",
        ["status", "grading_started_at", "attempted_at"],
    )


def downgrade() -> None:
    """Remove the grading worker lease while retaining attempt results."""
    op.drop_index("ix_task_attempts_grading_queue", table_name="task_attempts")
    op.drop_column("task_attempts", "grading_lease_token")
    op.drop_column("task_attempts", "grading_started_at")
