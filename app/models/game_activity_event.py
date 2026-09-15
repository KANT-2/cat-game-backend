from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GameActivityEvent(Base):
    """Append-only, privacy-minimal evidence of an authenticated game activity."""

    __tablename__ = "game_activity_events"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "event_type = 'GAME_ENTERED'",
            name="ck_game_activity_events_event_type",
        ),
        Index("ix_game_activity_events_occurred_at", "occurred_at"),
        Index("ix_game_activity_events_user_occurred_at", "user_id", "occurred_at"),
        Index("ix_game_activity_events_type_occurred_at", "event_type", "occurred_at"),
    )
