from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserLearningTier(Base):
    __tablename__ = "user_learning_tiers"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    current_tier: Mapped[str] = mapped_column(String, nullable=False, default="BRONZE")
    silver_unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gold_unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "domain", name="uq_user_learning_tiers_user_domain"),
        CheckConstraint("domain IN ('PYTHON', 'SQL')", name="ck_user_learning_tiers_domain"),
        CheckConstraint(
            "current_tier IN ('BRONZE', 'SILVER', 'GOLD')",
            name="ck_user_learning_tiers_current_tier",
        ),
    )
