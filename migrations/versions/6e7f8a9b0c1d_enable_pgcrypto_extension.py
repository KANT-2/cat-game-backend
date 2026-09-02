"""enable pgcrypto extension

Revision ID: 6e7f8a9b0c1d
Revises: 4fc9c8f005f1
Create Date: 2026-09-02 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6e7f8a9b0c1d"
down_revision: str | Sequence[str] | None = "4fc9c8f005f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Ensure existing databases also have the UUID extension."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    """Keep the shared extension because other schemas may depend on it."""
