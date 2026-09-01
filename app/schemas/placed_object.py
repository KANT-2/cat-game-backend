import uuid
from app.schemas.base import ReadSchema


class PlacedObjectRead(ReadSchema):
    item_public_id: uuid.UUID
    position_data: dict