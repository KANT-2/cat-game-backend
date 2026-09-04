import uuid

from pydantic import BaseModel, Field

from app.schemas.base import ReadSchema
from app.schemas.task import TaskRead


class RoomCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    max_participants: int = Field(ge=2, le=20)


class RoomJoin(BaseModel):
    team_name: str | None = Field(default=None, max_length=50)


class ReadyUpdate(BaseModel):
    is_ready: bool


class RoomStart(BaseModel):
    task_public_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)


class ParticipantView(BaseModel):
    user_public_id: uuid.UUID
    username: str
    team_name: str | None
    current_score: int
    is_ready: bool


class BattleTaskView(BaseModel):
    room_task_public_id: uuid.UUID
    task_order: int
    task: TaskRead


class BattleRoomRead(ReadSchema):
    host_user_public_id: uuid.UUID
    title: str
    status: str
    max_participants: int
    participants: list[ParticipantView]
    tasks: list[BattleTaskView]
    winner_user_public_ids: list[uuid.UUID]
