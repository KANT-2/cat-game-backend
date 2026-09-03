"""merge Part 2 learning and main migration heads

Revision ID: c8f4e2a1b6d9
Revises: 7d19cc4a44d5, a31f20c72b11
Create Date: 2026-09-03
"""

from collections.abc import Sequence

revision: str = "c8f4e2a1b6d9"
down_revision: str | Sequence[str] | None = ("7d19cc4a44d5", "a31f20c72b11")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the Part 2 and main migration histories."""


def downgrade() -> None:
    """Split the histories back into their two parent heads."""
