from datetime import date

from pydantic import BaseModel


class LearningDailyStatsRead(BaseModel):
    """One player's own submission activity for a single game-local day."""

    game_date: date
    distinct_tasks_attempted: int
    attempts_submitted: int
    attempts_completed: int
    correct_attempts: int
    incorrect_attempts: int
    hints_used: int
    coins_awarded: int
