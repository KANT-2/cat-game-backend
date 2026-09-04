"""add balance cost default

Revision ID: be8999b8f41e
Revises: 6e7f8a9b0c1d
Create Date: 2026-09-02 19:19:19.991113

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "be8999b8f41e"
down_revision: str | Sequence[str] | None = "6e7f8a9b0c1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "gacha_executions",
        "balance_cost",
        existing_type=sa.Integer(),
        server_default=sa.text("0"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "gacha_executions",
        "balance_cost",
        existing_type=sa.Integer(),
        server_default=None,
        existing_nullable=False,
    )
