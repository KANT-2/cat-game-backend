"""add shared authentication rate limits

Revision ID: e5f8a1b2c3d4
Revises: d4e7f0a3b6c9
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f8a1b2c3d4"
down_revision: str | Sequence[str] | None = "d4e7f0a3b6c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store hashed authentication throttle buckets shared by every API instance."""
    op.create_table(
        "auth_rate_limits",
        sa.Column("bucket_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("public_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index(
        "uq_auth_rate_limits_bucket_hash",
        "auth_rate_limits",
        ["bucket_hash"],
        unique=True,
    )
    op.create_index("ix_auth_rate_limits_updated_at", "auth_rate_limits", ["updated_at"])


def downgrade() -> None:
    """Remove shared authentication throttle state."""
    op.drop_index("ix_auth_rate_limits_updated_at", table_name="auth_rate_limits")
    op.drop_index("uq_auth_rate_limits_bucket_hash", table_name="auth_rate_limits")
    op.drop_table("auth_rate_limits")
