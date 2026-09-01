import uuid

from app.schemas.base import ReadSchema


class RoomTaskRead(ReadSchema):
    task_public_id: uuid.UUID
    task_order: int
