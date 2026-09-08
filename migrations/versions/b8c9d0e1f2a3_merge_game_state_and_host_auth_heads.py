"""merge authoritative game state and host authentication heads

Revision ID: b8c9d0e1f2a3
Revises: a7c8d9e0f1b2, 8a91c3d4e5f6
Create Date: 2026-09-06
"""

from collections.abc import Sequence

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = ("a7c8d9e0f1b2", "8a91c3d4e5f6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the authoritative game state and host authentication histories."""


def downgrade() -> None:
    """Split the histories back into their two parent heads."""
