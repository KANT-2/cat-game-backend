from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TaskPresentation(Base):
    """A stable presentation mode and option order for one learner task session."""

    __tablename__ = "task_presentations"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    context_type: Mapped[str] = mapped_column(String, nullable=False, default="LEARNING")
    presentation_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    correct_option: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "presentation_type IN ('CODE', 'MULTIPLE_CHOICE')",
            name="ck_task_presentations_type",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'COMPLETED')",
            name="ck_task_presentations_status",
        ),
        CheckConstraint(
            "(presentation_type = 'CODE' AND options IS NULL AND correct_option IS NULL) OR "
            "(presentation_type = 'MULTIPLE_CHOICE' AND options IS NOT NULL "
            "AND correct_option IS NOT NULL)",
            name="ck_task_presentations_options",
        ),
        Index(
            "uq_task_presentations_active",
            "user_id",
            "task_id",
            "context_type",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )
