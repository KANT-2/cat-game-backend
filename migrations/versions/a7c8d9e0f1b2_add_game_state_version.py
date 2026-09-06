"""add monotonic game state version

Revision ID: a7c8d9e0f1b2
Revises: f6a9b2c3d4e5
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c8d9e0f1b2"
down_revision: str | Sequence[str] | None = "f6a9b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the player-owned version used to order authoritative snapshots."""
    op.add_column(
        "users",
        sa.Column("state_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.create_check_constraint(
        "ck_users_state_version_positive",
        "users",
        "state_version >= 1",
    )


def downgrade() -> None:
    """Remove snapshot ordering metadata without changing player state."""
    op.drop_constraint("ck_users_state_version_positive", "users", type_="check")
    op.drop_column("users", "state_version")
