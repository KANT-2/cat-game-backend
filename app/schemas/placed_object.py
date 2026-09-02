import uuid
from typing import Protocol

from app.schemas.base import ReadSchema


class _PlacedObjectReadSource(Protocol):
    public_id: uuid.UUID
    position_data: dict


class PlacedObjectRead(ReadSchema):
    item_public_id: uuid.UUID
    position_data: dict


def to_placed_object_read(
    placed_object: _PlacedObjectReadSource,
    *,
    item_public_id: uuid.UUID,
) -> PlacedObjectRead:
    return PlacedObjectRead(
        public_id=placed_object.public_id,
        item_public_id=item_public_id,
        position_data=placed_object.position_data,
    )
