"""add privacy-minimal game statistics foundation

Revision ID: 1a2b3c4d5e6f
Revises: 0f1e2d3c4b5a
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1a2b3c4d5e6f"
down_revision: str | Sequence[str] | None = "0f1e2d3c4b5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "game_activity_events",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "occurred_at",
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
        sa.CheckConstraint(
            "event_type = 'GAME_ENTERED'",
            name="ck_game_activity_events_event_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index(
        "ix_game_activity_events_occurred_at",
        "game_activity_events",
        ["occurred_at"],
    )
    op.create_index(
        "ix_game_activity_events_user_occurred_at",
        "game_activity_events",
        ["user_id", "occurred_at"],
    )
    op.create_index(
        "ix_game_activity_events_type_occurred_at",
        "game_activity_events",
        ["event_type", "occurred_at"],
    )
    op.create_index("ix_task_attempts_attempted_at", "task_attempts", ["attempted_at"])
    op.create_index(
        "ix_task_attempts_user_attempted_at",
        "task_attempts",
        ["user_id", "attempted_at"],
    )
    _create_views()


def _create_views() -> None:
    op.execute(
        """
        CREATE VIEW analytics_daily_game_statistics AS
        WITH entry_stats AS (
            SELECT
                (occurred_at AT TIME ZONE 'Asia/Seoul')::date AS game_date,
                COUNT(*)::integer AS game_entries
            FROM game_activity_events
            WHERE event_type = 'GAME_ENTERED'
            GROUP BY 1
        ),
        attempt_stats AS (
            SELECT
                (attempted_at AT TIME ZONE 'Asia/Seoul')::date AS game_date,
                COUNT(DISTINCT user_id)::integer AS active_learners,
                COUNT(*)::integer AS attempts_submitted,
                COUNT(*) FILTER (WHERE status = 'COMPLETED')::integer AS attempts_completed,
                COUNT(*) FILTER (WHERE status = 'COMPLETED' AND is_correct IS TRUE)::integer
                    AS correct_attempts,
                COUNT(*) FILTER (WHERE status = 'COMPLETED' AND is_correct IS FALSE)::integer
                    AS incorrect_attempts,
                COUNT(*) FILTER (WHERE status = 'FAILED')::integer AS grading_failed_attempts,
                COUNT(*) FILTER (WHERE used_hint IS TRUE)::integer AS hints_used,
                COALESCE(SUM(coins_awarded), 0)::integer AS coins_awarded
            FROM task_attempts
            GROUP BY 1
        ),
        active_users AS (
            SELECT game_date, COUNT(DISTINCT user_id)::integer AS daily_active_users
            FROM (
                SELECT (occurred_at AT TIME ZONE 'Asia/Seoul')::date AS game_date, user_id
                FROM game_activity_events
                WHERE event_type = 'GAME_ENTERED'
                UNION ALL
                SELECT (attempted_at AT TIME ZONE 'Asia/Seoul')::date AS game_date, user_id
                FROM task_attempts
            ) activity
            GROUP BY game_date
        )
        SELECT
            active_users.game_date,
            active_users.daily_active_users,
            COALESCE(entry_stats.game_entries, 0)::integer AS game_entries,
            COALESCE(attempt_stats.active_learners, 0)::integer AS active_learners,
            COALESCE(attempt_stats.attempts_submitted, 0)::integer AS attempts_submitted,
            COALESCE(attempt_stats.attempts_completed, 0)::integer AS attempts_completed,
            COALESCE(attempt_stats.correct_attempts, 0)::integer AS correct_attempts,
            COALESCE(attempt_stats.incorrect_attempts, 0)::integer AS incorrect_attempts,
            COALESCE(attempt_stats.grading_failed_attempts, 0)::integer
                AS grading_failed_attempts,
            COALESCE(attempt_stats.hints_used, 0)::integer AS hints_used,
            COALESCE(attempt_stats.coins_awarded, 0)::integer AS coins_awarded
        FROM active_users
        LEFT JOIN entry_stats USING (game_date)
        LEFT JOIN attempt_stats USING (game_date)
        """
    )
    op.execute(
        """
        CREATE VIEW analytics_user_daily_learning_statistics AS
        SELECT
            (attempt.attempted_at AT TIME ZONE 'Asia/Seoul')::date AS game_date,
            users.public_id AS user_public_id,
            users.username,
            COUNT(DISTINCT attempt.task_id)::integer AS distinct_tasks_attempted,
            COUNT(*)::integer AS attempts_submitted,
            COUNT(*) FILTER (WHERE attempt.status = 'COMPLETED')::integer
                AS attempts_completed,
            COUNT(*) FILTER (
                WHERE attempt.status = 'COMPLETED' AND attempt.is_correct IS TRUE
            )::integer AS correct_attempts,
            COUNT(*) FILTER (
                WHERE attempt.status = 'COMPLETED' AND attempt.is_correct IS FALSE
            )::integer AS incorrect_attempts,
            COUNT(*) FILTER (WHERE attempt.status = 'FAILED')::integer
                AS grading_failed_attempts,
            COUNT(*) FILTER (WHERE attempt.used_hint IS TRUE)::integer AS hints_used,
            COALESCE(SUM(attempt.coins_awarded), 0)::integer AS coins_awarded
        FROM task_attempts attempt
        JOIN users ON users.id = attempt.user_id
        GROUP BY 1, users.public_id, users.username
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW analytics_user_daily_learning_statistics")
    op.execute("DROP VIEW analytics_daily_game_statistics")
    op.drop_index("ix_task_attempts_user_attempted_at", table_name="task_attempts")
    op.drop_index("ix_task_attempts_attempted_at", table_name="task_attempts")
    op.drop_index(
        "ix_game_activity_events_type_occurred_at",
        table_name="game_activity_events",
    )
    op.drop_index(
        "ix_game_activity_events_user_occurred_at",
        table_name="game_activity_events",
    )
    op.drop_index("ix_game_activity_events_occurred_at", table_name="game_activity_events")
    op.drop_table("game_activity_events")
