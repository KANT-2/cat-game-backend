from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserCat(Base):
    __tablename__ = "user_cats"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    cat_id: Mapped[int | None] = mapped_column(ForeignKey("cats.id"), nullable=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("user_id", "cat_id", name="uq_user_cats_user_cat"),
        UniqueConstraint("user_id", "item_id", name="uq_user_cats_user_item"),
        CheckConstraint(
            "(cat_id IS NOT NULL) <> (item_id IS NOT NULL)",
            name="ck_user_cats_cat_xor_item",
        ),
        CheckConstraint("quantity > 0", name="ck_user_cats_quantity_positive"),
        CheckConstraint("cat_id IS NULL OR quantity = 1", name="ck_user_cats_cat_quantity_one"),
    )
