import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, DbSession
from app.models.concept import Concept
from app.modules.daily_mission.service import (
    DailyMissionError,
    claim_reward,
    daily_tasks,
    get_or_create_daily,
)
from app.schemas.daily_mission import DailyMissionRead, DailyTaskRead
from app.schemas.task import to_task_read

router = APIRouter(prefix="/daily", tags=["daily"])


def payload(db, attendance) -> DailyMissionRead:
    rows = daily_tasks(db, attendance)
    return DailyMissionRead(
        public_id=attendance.public_id,
        check_in_date=attendance.check_in_date,
        streak_count=attendance.streak_count,
        reward_claimed=attendance.daily_reward_claimed_at is not None,
        tasks=[
            DailyTaskRead(
                attendance_task_public_id=link.public_id,
                task_order=link.task_order,
                is_completed=link.is_completed,
                task=to_task_read(task, db.get(Concept, task.concept_id)),
            )
            for link, task in rows
        ],
    )


@router.get("/today", response_model=DailyMissionRead)
def today(db: DbSession, user: CurrentUser) -> DailyMissionRead:
    try:
        from app.core.config import settings

        game_date = datetime.now(ZoneInfo(settings.game_timezone)).date()
        return payload(db, get_or_create_daily(db, user, game_date))
    except DailyMissionError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/{attendance_public_id}/reward", response_model=DailyMissionRead)
def reward(attendance_public_id: uuid.UUID, db: DbSession, user: CurrentUser) -> DailyMissionRead:
    try:
        return payload(db, claim_reward(db, user, attendance_public_id))
    except DailyMissionError as exc:
        db.rollback()
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if "not configured" in str(exc)
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(code, str(exc)) from exc
