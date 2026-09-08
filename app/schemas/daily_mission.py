import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.base import ReadSchema
from app.schemas.task import TaskRead


class DailyTaskRead(BaseModel):
    attendance_task_public_id: uuid.UUID
    task_order: int
    is_completed: bool
    task: TaskRead


class DailyMissionRead(ReadSchema):
    check_in_date: date
    streak_count: int
    reward_claimed: bool
    tasks: list[DailyTaskRead]
