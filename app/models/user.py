from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="STUDENT")

    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mileage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    house_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    wallpaper_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    floor_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
        CheckConstraint("balance >= 0", name="ck_users_balance_nonneg"),
        CheckConstraint("mileage >= 0", name="ck_users_mileage_nonneg"),
    )
