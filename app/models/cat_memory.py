from datetime import datetime
from sqlalchemy import Text, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class CatMemory(Base):
    __tablename__ = "cat_memories"

    user_cat_id: Mapped[int] = mapped_column(
        ForeignKey("user_cats.id", ondelete="RESTRICT"), nullable=False
    )
    context_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )