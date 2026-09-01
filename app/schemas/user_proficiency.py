import uuid

from app.schemas.base import ReadSchema


class AttendanceTaskRead(ReadSchema):
    task_public_id: uuid.UUID
    task_order: int
    is_completed: bool
