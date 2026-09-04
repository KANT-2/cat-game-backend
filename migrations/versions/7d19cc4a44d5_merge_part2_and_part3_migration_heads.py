"""merge part2 and part3 migration heads

Revision ID: 7d19cc4a44d5
Revises: d2a4c1b9e730, f6a7b8c9d0e1
Create Date: 2026-09-03 18:03:39.024445

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "7d19cc4a44d5"
down_revision: str | Sequence[str] | None = ("d2a4c1b9e730", "f6a7b8c9d0e1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
