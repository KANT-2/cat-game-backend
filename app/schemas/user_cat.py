import uuid
from typing import Protocol

from app.schemas.base import ReadSchema


class _UserCatReadSource(Protocol):
    public_id: uuid.UUID
    quantity: int


class UserCatRead(ReadSchema):
    cat_public_id: uuid.UUID | None
    item_public_id: uuid.UUID | None
    quantity: int


def to_user_cat_read(
    user_cat: _UserCatReadSource,
    *,
    cat_public_id: uuid.UUID | None,
    item_public_id: uuid.UUID | None,
) -> UserCatRead:
    return UserCatRead(
        public_id=user_cat.public_id,
        cat_public_id=cat_public_id,
        item_public_id=item_public_id,
        quantity=user_cat.quantity,
    )
