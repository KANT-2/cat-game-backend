import uuid
from app.schemas.base import ReadSchema


class RoomRead(ReadSchema):
    host_user_public_id: uuid.UUID
    title: str
    status: str
    max_participants: int