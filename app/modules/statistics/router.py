from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import CurrentUser, DbSession, verify_tasks_api_key
from app.core.time import game_today
from app.modules.statistics.schemas import (
    DailyGameStatisticsRead,
    MyDailyLearningStatisticsRead,
    UserDailyLearningStatisticsRead,
)
from app.modules.statistics.service import (
    daily_game_statistics,
    user_daily_learning_statistics,
    user_daily_learning_statistics_for_user,
)

router = APIRouter(
    prefix="/statistics",
    tags=["statistics"],
    dependencies=[Depends(verify_tasks_api_key)],
)

# Session-authenticated statistics for players: no team API key, scoped to the caller
# where the data is personal. Kept separate from `router` above so its routes don't
# inherit the team-key-only dependency.
public_router = APIRouter(prefix="/statistics", tags=["statistics"])

StatisticsDate = Annotated[date, Query()]
OptionalStatisticsDate = Annotated[date | None, Query()]

DEFAULT_LOOKBACK_DAYS = 14


def _validate_range(date_from: date, date_to: date) -> None:
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date-from-must-not-exceed-date-to")
    if (date_to - date_from).days > 366:
        raise HTTPException(status_code=422, detail="statistics-range-too-large")


def _resolve_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    resolved_to = date_to or game_today()
    resolved_from = date_from or resolved_to - timedelta(days=DEFAULT_LOOKBACK_DAYS - 1)
    _validate_range(resolved_from, resolved_to)
    return resolved_from, resolved_to


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


@public_router.get("/public/daily", response_model=list[DailyGameStatisticsRead])
def read_public_daily_statistics(
    db: DbSession,
    user: CurrentUser,
    date_from: OptionalStatisticsDate = None,
    date_to: OptionalStatisticsDate = None,
) -> list[dict]:
    resolved_from, resolved_to = _resolve_range(date_from, date_to)
    return daily_game_statistics(db, resolved_from, resolved_to)


@public_router.get("/me/daily", response_model=list[MyDailyLearningStatisticsRead])
def read_my_daily_statistics(
    db: DbSession,
    user: CurrentUser,
    date_from: OptionalStatisticsDate = None,
    date_to: OptionalStatisticsDate = None,
) -> list[dict]:
    resolved_from, resolved_to = _resolve_range(date_from, date_to)
    return user_daily_learning_statistics_for_user(db, user.public_id, resolved_from, resolved_to)
