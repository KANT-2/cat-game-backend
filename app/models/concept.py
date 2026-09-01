from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Concept(Base):
    __tablename__ = "concepts"

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)