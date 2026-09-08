from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    homepage_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="STUDENT")
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mileage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    house_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    starter_pack_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    wallpaper_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    floor_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    active_cat_id: Mapped[int | None] = mapped_column(ForeignKey("cats.id"), nullable=True)
    game_settings: Mapped[dict[str, bool]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "bgmEnabled": True,
            "bgmVolume": 70,
            "effectsEnabled": True,
            "effectsVolume": 80,
            "reducedMotion": False,
        },
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    learning_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
        CheckConstraint("balance >= 0", name="ck_users_balance_nonneg"),
        CheckConstraint("mileage >= 0", name="ck_users_mileage_nonneg"),
        CheckConstraint("starter_pack_version >= 0", name="ck_users_starter_pack_version_nonneg"),
        CheckConstraint("state_version >= 1", name="ck_users_state_version_positive"),
    )

    def advance_state_version(self) -> None:
        """Advance the monotonic version in the same transaction as a game-state mutation."""
        self.state_version = (self.state_version or 1) + 1
