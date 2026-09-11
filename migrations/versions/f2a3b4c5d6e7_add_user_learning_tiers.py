"""add user learning tiers

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_learning_tiers",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("current_tier", sa.String(), nullable=False),
        sa.Column("silver_unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gold_unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("public_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("domain IN ('PYTHON', 'SQL')", name="ck_user_learning_tiers_domain"),
        sa.CheckConstraint("current_tier IN ('BRONZE', 'SILVER', 'GOLD')", name="ck_user_learning_tiers_current_tier"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("user_id", "domain", name="uq_user_learning_tiers_user_domain"),
    )


def downgrade() -> None:
    op.drop_table("user_learning_tiers")
