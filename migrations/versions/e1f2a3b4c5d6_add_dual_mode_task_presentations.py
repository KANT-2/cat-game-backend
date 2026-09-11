"""add dual-mode task presentations

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("multiple_choice_prompt", sa.Text(), nullable=True))
    op.execute(
        "UPDATE tasks SET multiple_choice_prompt = description "
        "WHERE options IS NOT NULL AND correct_option IS NOT NULL"
    )
    op.drop_constraint("ck_tasks_grading_metadata", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_grading_metadata",
        "tasks",
        "(type = 'MULTIPLE_CHOICE' AND options IS NOT NULL AND correct_option IS NOT NULL) OR "
        "(multiple_choice_prompt IS NULL AND options IS NULL AND correct_option IS NULL) OR "
        "(multiple_choice_prompt IS NOT NULL AND options IS NOT NULL AND correct_option IS NOT NULL)",
    )
    op.create_table(
        "task_presentations",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("context_type", sa.String(), nullable=False),
        sa.Column("presentation_type", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correct_option", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("public_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "presentation_type IN ('CODE', 'MULTIPLE_CHOICE')",
            name="ck_task_presentations_type",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'COMPLETED')",
            name="ck_task_presentations_status",
        ),
        sa.CheckConstraint(
            "(presentation_type = 'CODE' AND options IS NULL AND correct_option IS NULL) OR "
            "(presentation_type = 'MULTIPLE_CHOICE' AND options IS NOT NULL AND correct_option IS NOT NULL)",
            name="ck_task_presentations_options",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index(
        "uq_task_presentations_active",
        "task_presentations",
        ["user_id", "task_id", "context_type"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.add_column("task_attempts", sa.Column("presentation_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_task_attempts_presentation",
        "task_attempts",
        "task_presentations",
        ["presentation_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_task_attempts_presentation", "task_attempts", type_="foreignkey")
    op.drop_column("task_attempts", "presentation_id")
    op.drop_index("uq_task_presentations_active", table_name="task_presentations")
    op.drop_table("task_presentations")
    op.drop_constraint("ck_tasks_grading_metadata", "tasks", type_="check")
    op.execute(
        "UPDATE tasks SET options = NULL, correct_option = NULL "
        "WHERE type = 'CODE'"
    )
    op.create_check_constraint(
        "ck_tasks_grading_metadata",
        "tasks",
        "(type = 'CODE' AND options IS NULL AND correct_option IS NULL) OR "
        "(type = 'MULTIPLE_CHOICE' AND options IS NOT NULL AND correct_option IS NOT NULL)",
    )
    op.drop_column("tasks", "multiple_choice_prompt")
