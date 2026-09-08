"""add homepage user id

Revision ID: 8a91c3d4e5f6
Revises: c8f4e2a1b6d9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8a91c3d4e5f6"
down_revision: str | Sequence[str] | None = "c8f4e2a1b6d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("homepage_user_id", sa.BigInteger(), nullable=True))
    op.create_unique_constraint("uq_users_homepage_user_id", "users", ["homepage_user_id"])


def downgrade() -> None:
    op.drop_constraint("uq_users_homepage_user_id", "users", type_="unique")
    op.drop_column("users", "homepage_user_id")
