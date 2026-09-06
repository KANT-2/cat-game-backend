import json
import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, DbSession
from app.models.task import Task
from app.modules.grading.service import SubmissionError, create_attempt, get_attempt
from app.schemas.task_attempt import (
    GradingResultRead,
    TaskAttemptAccepted,
    TaskAttemptCreate,
    TaskAttemptRead,
)

router = APIRouter(prefix="/attempts", tags=["grading"])


@router.post("", response_model=TaskAttemptAccepted, status_code=status.HTTP_202_ACCEPTED)
def submit(payload: TaskAttemptCreate, db: DbSession, user: CurrentUser):
    try:
        attempt = create_attempt(db, payload, user)
    except SubmissionError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TaskAttemptAccepted(public_id=attempt.public_id, status="PENDING")


@router.get("/{attempt_public_id}", response_model=TaskAttemptRead)
def result(attempt_public_id: uuid.UUID, db: DbSession, user: CurrentUser) -> TaskAttemptRead:
    attempt = get_attempt(db, attempt_public_id, user)
    if attempt is None:
        raise HTTPException(status_code=404, detail="attempt not found")
    task = db.get(Task, attempt.task_id)
    return TaskAttemptRead(
        public_id=attempt.public_id,
        task_public_id=task.public_id,
        context_type=attempt.context_type,
        status=attempt.status,
        is_correct=attempt.is_correct,
        used_hint=attempt.used_hint,
        attempted_at=attempt.attempted_at,
        result_detail=_read_public_result(attempt.result_detail),
        coins_awarded=attempt.coins_awarded,
    )


def _read_public_result(raw: str | None) -> GradingResultRead | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError("grading result must be an object")
        return GradingResultRead.model_validate(
            {
                "verdict": value.get("verdict", "SYSTEM_ERROR"),
                "passed": value.get("passed", 0),
                "total": value.get("total", 0),
            }
        )
    except (TypeError, ValueError):
        return GradingResultRead(verdict="SYSTEM_ERROR", passed=0, total=0)
