from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RoomParticipant(Base):
    __tablename__ = "room_participants"

    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    team_name: Mapped[str | None] = mapped_column(String, nullable=True)
    current_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_participants_room_user"),
        CheckConstraint("current_score >= 0", name="ck_room_participants_score_nonneg"),
    )
