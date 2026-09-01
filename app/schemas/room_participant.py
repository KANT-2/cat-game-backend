import uuid

from app.schemas.base import ReadSchema


class RoomParticipantRead(ReadSchema):
    user_public_id: uuid.UUID
    team_name: str | None
    current_score: int
    is_ready: bool
