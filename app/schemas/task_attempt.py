import uuid
from datetime import datetime

from app.schemas.base import ReadSchema


class TaskAttemptRead(ReadSchema):
    task_public_id: uuid.UUID
    context_type: str
    submitted_code: str
    status: str
    is_correct: bool | None
    used_hint: bool
    attempted_at: datetime
