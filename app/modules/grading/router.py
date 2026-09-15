import json
import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, DbSession
from app.core.exceptions import IdempotencyConflictError
from app.models.task import Task
from app.modules.grading.service import SubmissionError, create_attempt, get_attempt, grade_attempt
from app.modules.learning.presentation import start_task_presentation, to_presented_task
from app.schemas.task_attempt import (
    GradingResultDetail,
    TaskAttemptAccepted,
    TaskAttemptCreate,
    TaskAttemptRead,
    TaskPresentationRead,
    TaskPresentationStart,
    to_task_attempt_read,
)

router = APIRouter(prefix="/attempts", tags=["grading"])


@router.post("/presentations", response_model=TaskPresentationRead)
def start_presentation(payload: TaskPresentationStart, db: DbSession, user: CurrentUser):
    try:
        presentation, task, concept = start_task_presentation(
            db,
            payload.task_public_id,
            user,
            preferred_presentation_type=payload.preferred_presentation_type,
        )
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TaskPresentationRead(
        presentation_public_id=presentation.public_id,
        task=to_presented_task(presentation, task, concept),
    )


@router.post("", response_model=TaskAttemptAccepted, status_code=status.HTTP_202_ACCEPTED)
def submit(payload: TaskAttemptCreate, db: DbSession, user: CurrentUser):
    try:
        attempt = create_attempt(db, payload, user)
    except IdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="idempotency-conflict") from exc
    except SubmissionError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # Learning MCQs need no sandbox. Grade them immediately so a worker delay or
    # outage cannot turn a simple option selection into a client-side timeout.
    if payload.context_type == "LEARNING" and payload.selected_option is not None:
        grade_attempt(attempt.public_id)
    return TaskAttemptAccepted(public_id=attempt.public_id, status="PENDING")


@router.get("/{attempt_public_id}", response_model=TaskAttemptRead)
def result(attempt_public_id: uuid.UUID, db: DbSession, user: CurrentUser) -> TaskAttemptRead:
    attempt = get_attempt(db, attempt_public_id, user)
    if attempt is None:
        raise HTTPException(status_code=404, detail="attempt not found")
    task = db.get(Task, attempt.task_id)
    return to_task_attempt_read(attempt, task)


def _read_public_result(raw: str | None) -> GradingResultDetail | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError("grading result must be an object")
        return GradingResultDetail.model_validate(
            {
                "verdict": value.get("verdict", "SYSTEM_ERROR"),
                "passed": value.get("passed", 0),
                "total": value.get("total", 0),
            }
        )
    except (TypeError, ValueError):
        return GradingResultDetail(verdict="SYSTEM_ERROR", passed=0, total=0)
