from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AttendanceTask(Base):
    __tablename__ = "attendance_tasks"

    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendances.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    task_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("attendance_id", "task_id", name="uq_attendance_tasks_attendance_task"),
        UniqueConstraint(
            "attendance_id", "task_order", name="uq_attendance_tasks_attendance_order"
        ),
        UniqueConstraint("id", "task_id", name="uq_attendance_tasks_id_task_id"),
        CheckConstraint("task_order > 0", name="ck_attendance_tasks_order_positive"),
    )
