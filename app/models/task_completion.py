from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TaskCompletion(Base):
    __tablename__ = "task_completions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    first_attempt_id: Mapped[int] = mapped_column(ForeignKey("task_attempts.id"), nullable=False)
    coins_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "task_id", name="uq_task_completions_user_task"),
        CheckConstraint("coins_awarded >= 0", name="ck_task_completions_coins_awarded_nonneg"),
    )
