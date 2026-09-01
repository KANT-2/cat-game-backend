from datetime import date, datetime
from app.schemas.base import ReadSchema


class AttendanceRead(ReadSchema):
    check_in_date: date
    streak_count: int
    daily_reward_claimed_at: datetime | None