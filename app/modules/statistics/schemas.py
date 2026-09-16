import uuid
from datetime import date

from pydantic import BaseModel


class DailyGameStatisticsRead(BaseModel):
    game_date: date
    daily_active_users: int
    game_entries: int
    active_learners: int
    attempts_submitted: int
    attempts_completed: int
    correct_attempts: int
    incorrect_attempts: int
    grading_failed_attempts: int
    hints_used: int
    coins_awarded: int


class UserDailyLearningStatisticsRead(BaseModel):
    game_date: date
    user_public_id: uuid.UUID
    username: str
    distinct_tasks_attempted: int
    attempts_submitted: int
    attempts_completed: int
    correct_attempts: int
    incorrect_attempts: int
    grading_failed_attempts: int
    hints_used: int
    coins_awarded: int


class MyDailyLearningStatisticsRead(BaseModel):
    game_date: date
    distinct_tasks_attempted: int
    attempts_submitted: int
    attempts_completed: int
    correct_attempts: int
    incorrect_attempts: int
    grading_failed_attempts: int
    hints_used: int
    coins_awarded: int
