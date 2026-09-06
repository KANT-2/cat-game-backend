from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyRewardClaim(Base):
    __tablename__ = "daily_reward_claims"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    claim_date: Mapped[date] = mapped_column(Date, nullable=False)
    reward_key: Mapped[str] = mapped_column(String, nullable=False)
    coins_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "claim_date", "reward_key", name="uq_daily_reward_claim"),
        CheckConstraint(
            "reward_key IN ('solve-one', 'solve-three', 'finish-code', 'bonus')",
            name="ck_daily_reward_claims_reward_key",
        ),
        CheckConstraint("coins_awarded >= 0", name="ck_daily_reward_claims_coins_awarded_nonneg"),
    )
