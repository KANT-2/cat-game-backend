import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.base import ReadSchema


class TaskAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_public_id: uuid.UUID
    submitted_code: str
    context_type: Literal["LEARNING", "DAILY", "BATTLE"]
    used_hint: bool = False
    attendance_task_public_id: uuid.UUID | None = None
    room_task_public_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_context_links(self):
        if not self.submitted_code.strip():
            raise ValueError("submitted_code must not be blank")
        links = (self.attendance_task_public_id, self.room_task_public_id)
        expected = {
            "LEARNING": (False, False),
            "DAILY": (True, False),
            "BATTLE": (False, True),
        }[self.context_type]
        if tuple(value is not None for value in links) != expected:
            raise ValueError("context public_id combination is invalid")
        return self


class TaskAttemptAccepted(BaseModel):
    public_id: uuid.UUID
    status: Literal["PENDING"]


class TaskAttemptRead(ReadSchema):
    task_public_id: uuid.UUID
    context_type: str
    submitted_code: str
    status: str
    is_correct: bool | None
    used_hint: bool
    attempted_at: datetime
    result_detail: str | None = Field(default=None)
