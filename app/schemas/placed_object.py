import uuid
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import ReadSchema


class _PlacedObjectReadSource(Protocol):
    public_id: uuid.UUID
    position_data: dict


class PositionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    z: float = Field(allow_inf_nan=False)


class PlacedObjectCreate(BaseModel):
    item_public_id: uuid.UUID
    position_data: PositionData


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
