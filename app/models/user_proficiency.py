from sqlalchemy import Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class UserProficiency(Base):
    __tablename__ = "user_proficiency"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), nullable=False)
    proficiency_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "concept_id", name="uq_user_proficiency_user_concept"),
    )