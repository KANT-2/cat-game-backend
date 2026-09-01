from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RoomTask(Base):
    __tablename__ = "room_tasks"

    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    task_order: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("room_id", "task_id", name="uq_room_tasks_room_task"),
        UniqueConstraint("room_id", "task_order", name="uq_room_tasks_room_order"),
        UniqueConstraint("id", "task_id", name="uq_room_tasks_id_task_id"),
        CheckConstraint("task_order > 0", name="ck_room_tasks_order_positive"),
    )
