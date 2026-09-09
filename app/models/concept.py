from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Concept(Base):
    __tablename__ = "concepts"

    domain: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("domain IN ('PYTHON', 'SQL')", name="ck_concepts_domain"),
        UniqueConstraint("domain", "name", name="uq_concepts_domain_name"),
    )
