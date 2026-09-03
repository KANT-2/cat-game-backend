from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TaskAttempt(Base):
    __tablename__ = "task_attempts"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    attendance_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    room_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    context_type: Mapped[str] = mapped_column(String, nullable=False)
    submitted_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    used_hint: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    result_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["attendance_task_id", "task_id"],
            ["attendance_tasks.id", "attendance_tasks.task_id"],
            name="fk_task_attempts_attendance_task",
        ),
        ForeignKeyConstraint(
            ["room_task_id", "task_id"],
            ["room_tasks.id", "room_tasks.task_id"],
            name="fk_task_attempts_room_task",
        ),
        CheckConstraint(
            "(context_type = 'LEARNING' AND attendance_task_id IS NULL AND room_task_id IS NULL) OR "
            "(context_type = 'DAILY' AND attendance_task_id IS NOT NULL AND room_task_id IS NULL) OR "
            "(context_type = 'BATTLE' AND attendance_task_id IS NULL AND room_task_id IS NOT NULL)",
            name="ck_task_attempts_context_fk_match",
        ),
    )
