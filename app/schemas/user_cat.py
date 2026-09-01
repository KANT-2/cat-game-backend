import uuid

from app.schemas.base import ReadSchema


class UserCatRead(ReadSchema):
    cat_public_id: uuid.UUID | None
    item_public_id: uuid.UUID | None
    quantity: int
