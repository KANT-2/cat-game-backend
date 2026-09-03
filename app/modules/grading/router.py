import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.api.dependencies import CurrentUser, DbSession
from app.models.task import Task
from app.modules.grading.service import SubmissionError, create_attempt, get_attempt, grade_attempt
from app.schemas.task_attempt import TaskAttemptAccepted, TaskAttemptCreate

router = APIRouter(prefix="/attempts", tags=["grading"])


@router.post("", response_model=TaskAttemptAccepted, status_code=status.HTTP_202_ACCEPTED)
def submit(payload: TaskAttemptCreate, background: BackgroundTasks, db: DbSession, user: CurrentUser):
    try:
        attempt = create_attempt(db, payload, user)
    except SubmissionError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    background.add_task(grade_attempt, attempt.public_id)
    return TaskAttemptAccepted(public_id=attempt.public_id, status="PENDING")


@router.get("/{attempt_public_id}")
def result(attempt_public_id: uuid.UUID, db: DbSession, user: CurrentUser):
    attempt = get_attempt(db, attempt_public_id, user)
    if attempt is None:
        raise HTTPException(status_code=404, detail="attempt not found")
    task = db.get(Task, attempt.task_id)
    return {
        "public_id": attempt.public_id, "task_public_id": task.public_id,
        "context_type": attempt.context_type, "status": attempt.status,
        "is_correct": attempt.is_correct, "used_hint": attempt.used_hint,
        "attempted_at": attempt.attempted_at, "result_detail": attempt.result_detail,
    }
