"""rename placement rotation coordinate to z

Revision ID: e4f5a6b7c8d9
Revises: d2c3b4a5e6f7
Create Date: 2026-09-03 17:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: str | Sequence[str] | None = "d2c3b4a5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE placed_objects
        SET position_data =
            (position_data - 'rotation')
            || jsonb_build_object('z', position_data -> 'rotation')
        WHERE position_data ? 'rotation'
          AND NOT position_data ? 'z'
    """)
    op.execute("""
        UPDATE placed_objects
        SET position_data = position_data - 'rotation'
        WHERE position_data ? 'rotation'
          AND position_data ? 'z'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE placed_objects
        SET position_data =
            (position_data - 'z')
            || jsonb_build_object('rotation', position_data -> 'z')
        WHERE position_data ? 'z'
          AND NOT position_data ? 'rotation'
    """)
    op.execute("""
        UPDATE placed_objects
        SET position_data = position_data - 'z'
        WHERE position_data ? 'z'
          AND position_data ? 'rotation'
    """)
