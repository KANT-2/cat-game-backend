"""add stable game catalog keys and player presentation state

Revision ID: 91b4c7d8e2f0
Revises: c8f4e2a1b6d9
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "91b4c7d8e2f0"
down_revision: str | Sequence[str] | None = "c8f4e2a1b6d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add API-stable catalog identifiers and server-owned player choices."""
    op.add_column("cats", sa.Column("catalog_key", sa.String(), nullable=True))
    op.execute("UPDATE cats SET catalog_key = 'legacy-cat-' || id WHERE catalog_key IS NULL")
    op.alter_column("cats", "catalog_key", nullable=False)
    op.create_unique_constraint("uq_cats_catalog_key", "cats", ["catalog_key"])

    op.add_column("items", sa.Column("catalog_key", sa.String(), nullable=True))
    op.execute("UPDATE items SET catalog_key = 'legacy-item-' || id WHERE catalog_key IS NULL")
    op.alter_column("items", "catalog_key", nullable=False)
    op.create_unique_constraint("uq_items_catalog_key", "items", ["catalog_key"])

    op.add_column(
        "assets",
        sa.Column("is_home", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_check_constraint(
        "ck_assets_home_cat_only",
        "assets",
        "cat_id IS NOT NULL OR NOT is_home",
    )

    op.add_column("users", sa.Column("active_cat_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_active_cat_id_cats",
        "users",
        "cats",
        ["active_cat_id"],
        ["id"],
    )
    op.add_column(
        "users",
        sa.Column("starter_pack_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_users_starter_pack_version_nonneg",
        "users",
        "starter_pack_version >= 0",
    )
    op.add_column(
        "users",
        sa.Column(
            "game_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text(
                "'{\"bgmEnabled\": true, \"bgmVolume\": 70, "
                "\"effectsEnabled\": true, \"effectsVolume\": 80, "
                "\"reducedMotion\": false}'::jsonb"
            ),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove the server-owned player presentation state and catalog keys."""
    op.drop_column("users", "game_settings")
    op.drop_constraint("ck_users_starter_pack_version_nonneg", "users", type_="check")
    op.drop_column("users", "starter_pack_version")
    op.drop_constraint("fk_users_active_cat_id_cats", "users", type_="foreignkey")
    op.drop_column("users", "active_cat_id")

    op.drop_constraint("ck_assets_home_cat_only", "assets", type_="check")
    op.drop_column("assets", "is_home")

    op.drop_constraint("uq_items_catalog_key", "items", type_="unique")
    op.drop_column("items", "catalog_key")

    op.drop_constraint("uq_cats_catalog_key", "cats", type_="unique")
    op.drop_column("cats", "catalog_key")
