"""add authoritative learning and daily reward records

Revision ID: b2c5d8e1f4a7
Revises: 91b4c7d8e2f0
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c5d8e1f4a7"
down_revision: str | Sequence[str] | None = "91b4c7d8e2f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add immutable completion rewards and date-scoped reward claims."""
    op.add_column(
        "tasks",
        sa.Column("reward_coins", sa.Integer(), server_default="0", nullable=False),
    )
    op.execute(
        "UPDATE tasks SET reward_coins = CASE difficulty "
        "WHEN 'BRONZE' THEN 30 WHEN 'SILVER' THEN 60 WHEN 'GOLD' THEN 100 ELSE 0 END"
    )
    op.create_check_constraint("ck_tasks_reward_coins_nonneg", "tasks", "reward_coins >= 0")

    op.add_column(
        "task_attempts",
        sa.Column("coins_awarded", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_task_attempts_coins_awarded_nonneg",
        "task_attempts",
        "coins_awarded >= 0",
    )

    op.create_table(
        "task_completions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("first_attempt_id", sa.Integer(), nullable=False),
        sa.Column("coins_awarded", sa.Integer(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "public_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["first_attempt_id"], ["task_attempts.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "coins_awarded >= 0",
            name="ck_task_completions_coins_awarded_nonneg",
        ),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("user_id", "task_id", name="uq_task_completions_user_task"),
    )
    op.execute(
        "INSERT INTO task_completions "
        "(user_id, task_id, first_attempt_id, coins_awarded, completed_at) "
        "SELECT DISTINCT ON (user_id, task_id) user_id, task_id, id, 0, attempted_at "
        "FROM task_attempts WHERE status = 'COMPLETED' AND is_correct IS TRUE "
        "ORDER BY user_id, task_id, attempted_at, id"
    )
    op.create_table(
        "daily_reward_claims",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("claim_date", sa.Date(), nullable=False),
        sa.Column("reward_key", sa.String(), nullable=False),
        sa.Column("coins_awarded", sa.Integer(), nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "public_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "reward_key IN ('solve-one', 'solve-three', 'finish-code', 'bonus')",
            name="ck_daily_reward_claims_reward_key",
        ),
        sa.CheckConstraint(
            "coins_awarded >= 0",
            name="ck_daily_reward_claims_coins_awarded_nonneg",
        ),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("user_id", "claim_date", "reward_key", name="uq_daily_reward_claim"),
    )


def downgrade() -> None:
    """Remove learning completion and daily reward persistence."""
    op.drop_table("daily_reward_claims")
    op.drop_table("task_completions")
    op.drop_constraint("ck_task_attempts_coins_awarded_nonneg", "task_attempts", type_="check")
    op.drop_column("task_attempts", "coins_awarded")
    op.drop_constraint("ck_tasks_reward_coins_nonneg", "tasks", type_="check")
    op.drop_column("tasks", "reward_coins")
