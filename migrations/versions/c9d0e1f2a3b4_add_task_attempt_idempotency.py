"""add task attempt idempotency

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist one client request key and canonical payload hash per attempt."""
    op.add_column(
        "task_attempts",
        sa.Column(
            "request_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
    )
    op.add_column(
        "task_attempts",
        sa.Column(
            "request_hash",
            sa.String(length=64),
            server_default=sa.text("repeat('0', 64)"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_task_attempts_request_id",
        "task_attempts",
        ["request_id"],
    )


def downgrade() -> None:
    """Remove grading submission idempotency metadata."""
    op.drop_constraint("uq_task_attempts_request_id", "task_attempts", type_="unique")
    op.drop_column("task_attempts", "request_hash")
    op.drop_column("task_attempts", "request_id")
