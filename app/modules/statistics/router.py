from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import DbSession, verify_tasks_api_key
from app.modules.statistics.schemas import (
    DailyGameStatisticsRead,
    UserDailyLearningStatisticsRead,
)
from app.modules.statistics.service import daily_game_statistics, user_daily_learning_statistics

router = APIRouter(
    prefix="/statistics",
    tags=["statistics"],
    dependencies=[Depends(verify_tasks_api_key)],
)

StatisticsDate = Annotated[date, Query()]


def _validate_range(date_from: date, date_to: date) -> None:
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date-from-must-not-exceed-date-to")
    if (date_to - date_from).days > 366:
        raise HTTPException(status_code=422, detail="statistics-range-too-large")


@router.get("/daily", response_model=list[DailyGameStatisticsRead])
def read_daily_statistics(
    db: DbSession,
    date_from: StatisticsDate,
    date_to: StatisticsDate,
) -> list[dict]:
    _validate_range(date_from, date_to)
    return daily_game_statistics(db, date_from, date_to)


@router.get("/users/daily", response_model=list[UserDailyLearningStatisticsRead])
def read_user_daily_statistics(
    db: DbSession,
    date_from: StatisticsDate,
    date_to: StatisticsDate,
) -> list[dict]:
    _validate_range(date_from, date_to)
    return user_daily_learning_statistics(db, date_from, date_to)
