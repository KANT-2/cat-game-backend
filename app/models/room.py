from sqlalchemy import String, Integer, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Room(Base):
    __tablename__ = "rooms"

    host_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="WAITING")
    max_participants: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("max_participants > 0", name="ck_rooms_max_participants_positive"),
    )