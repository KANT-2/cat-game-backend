from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Attendance(Base):
    __tablename__ = "attendances"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    check_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    streak_count: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_reward_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "check_in_date", name="uq_attendances_user_date"),
        CheckConstraint("streak_count >= 1", name="ck_attendances_streak_positive"),
    )
