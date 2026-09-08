"""add learning reset timestamp

Revision ID: c3d6e9f2a5b8
Revises: b2c5d8e1f4a7
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d6e9f2a5b8"
down_revision: str | Sequence[str] | None = "b2c5d8e1f4a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a progress boundary while preserving immutable attempt and reward history."""
    op.add_column("users", sa.Column("learning_reset_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Remove the learning progress boundary."""
    op.drop_column("users", "learning_reset_at")
