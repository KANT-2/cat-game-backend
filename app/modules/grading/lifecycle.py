import json

from sqlalchemy.orm import Session

from app.models.attendance_task import AttendanceTask
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.modules.battle.service import record_attempt_result
from app.modules.grading.sandbox.runner import GradeResult
from app.modules.learning.proficiency import update_proficiency


def mark_running(db: Session, attempt: TaskAttempt) -> None:
    attempt.status = "RUNNING"
    db.commit()


def finish_attempt(
    db: Session,
    attempt: TaskAttempt,
    task: Task,
    result: GradeResult,
) -> None:
    attempt.status = "FAILED" if result.is_system_failure else "COMPLETED"
    attempt.is_correct = None if result.is_system_failure else result.is_correct
    attempt.result_detail = json.dumps(
        {"verdict": str(result.verdict), "detail": result.detail}
    )

    if attempt.is_correct is not None:
        update_proficiency(db, attempt.user_id, task.concept_id)
    if attempt.is_correct and attempt.context_type == "DAILY":
        attendance_task = db.get(AttendanceTask, attempt.attendance_task_id)
        if attendance_task is not None:
            attendance_task.is_completed = True
    if attempt.context_type == "BATTLE" and attempt.is_correct is not None:
        record_attempt_result(db, attempt)

    db.commit()


def fail_attempt(
    db: Session,
    attempt: TaskAttempt,
    verdict: str,
    detail: str,
) -> None:
    attempt.status = "FAILED"
    attempt.is_correct = None
    attempt.result_detail = json.dumps({"verdict": verdict, "detail": detail})
    db.commit()
