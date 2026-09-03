from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Task(Base):
    __tablename__ = "tasks"

    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str] = mapped_column(
        String, nullable=False, default="PYTHON", server_default=text("'PYTHON'")
    )
    difficulty: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    template_code: Mapped[str] = mapped_column(Text, nullable=False)
    test_cases: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    correct_option: Mapped[str | None] = mapped_column(String, nullable=True)
    hint_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("type IN ('CODE', 'MULTIPLE_CHOICE')", name="ck_tasks_type"),
        CheckConstraint("domain IN ('PYTHON', 'SQL')", name="ck_tasks_domain"),
        CheckConstraint("difficulty IN ('BRONZE', 'SILVER', 'GOLD')", name="ck_tasks_difficulty"),
        CheckConstraint(
            "(type = 'CODE' AND options IS NULL AND correct_option IS NULL) OR "
            "(type = 'MULTIPLE_CHOICE' AND options IS NOT NULL AND correct_option IS NOT NULL)",
            name="ck_tasks_grading_metadata",
        ),
    )
