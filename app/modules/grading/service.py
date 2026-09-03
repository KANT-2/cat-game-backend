import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.attendance import Attendance
from app.models.attendance_task import AttendanceTask
from app.models.room_participant import RoomParticipant
from app.models.room_task import RoomTask
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.models.user import User
from app.modules.grading.sandbox.runner import sandbox
from app.modules.grading.test_cases import TestCaseSpecError, parse_test_cases
from app.schemas.task_attempt import TaskAttemptCreate


class SubmissionError(ValueError):
    pass


def _by_public_id(db: Session, model, public_id: uuid.UUID):
    return db.scalar(select(model).where(model.public_id == public_id))


def create_attempt(db: Session, payload: TaskAttemptCreate, user: User) -> TaskAttempt:
    task = _by_public_id(db, Task, payload.task_public_id)
    if task is None or not task.is_active:
        raise SubmissionError("task not found")
    attendance_task = room_task = None
    if payload.context_type == "DAILY":
        attendance_task = _by_public_id(db, AttendanceTask, payload.attendance_task_public_id)
        owned = attendance_task and db.scalar(select(Attendance.id).where(
            Attendance.id == attendance_task.attendance_id, Attendance.user_id == user.id
        ))
        if not owned or attendance_task.task_id != task.id:
            raise SubmissionError("daily task not found")
    elif payload.context_type == "BATTLE":
        room_task = _by_public_id(db, RoomTask, payload.room_task_public_id)
        participant = room_task and db.scalar(select(RoomParticipant.id).where(
            RoomParticipant.room_id == room_task.room_id, RoomParticipant.user_id == user.id
        ))
        if not participant or room_task.task_id != task.id:
            raise SubmissionError("battle task not found")
    attempt = TaskAttempt(
        user_id=user.id, task_id=task.id,
        attendance_task_id=attendance_task.id if attendance_task else None,
        room_task_id=room_task.id if room_task else None,
        context_type=payload.context_type, submitted_code=payload.submitted_code,
        used_hint=payload.used_hint, status="PENDING", is_correct=None,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def _finish(db, attempt, is_correct, status, verdict, detail=None):
    attempt.status = status
    attempt.is_correct = is_correct
    attempt.result_detail = json.dumps({"verdict": str(verdict), "detail": detail})
    db.commit()


def grade_attempt(attempt_public_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        attempt = _by_public_id(db, TaskAttempt, attempt_public_id)
        if attempt is None or attempt.status != "PENDING":
            return
        attempt.status = "RUNNING"
        db.commit()
        task = db.get(Task, attempt.task_id)
        try:
            cases = parse_test_cases(task.test_cases)
        except TestCaseSpecError as exc:
            _finish(db, attempt, None, "FAILED", "TEST_CASE_SPEC_ERROR", str(exc))
            return
        result = sandbox.grade(attempt.submitted_code, cases)
        status = "FAILED" if result.is_system_failure else "COMPLETED"
        is_correct = None if result.is_system_failure else result.is_correct
        _finish(db, attempt, is_correct, status, result.verdict, result.detail)
        if is_correct and attempt.context_type == "DAILY":
            db.get(AttendanceTask, attempt.attendance_task_id).is_completed = True
            db.commit()
    except Exception as exc:  # noqa: BLE001 - background boundary must persist FAILED
        db.rollback()
        attempt = _by_public_id(db, TaskAttempt, attempt_public_id)
        if attempt:
            _finish(db, attempt, None, "FAILED", "SYSTEM_ERROR", str(exc))
    finally:
        db.close()


def get_attempt(db: Session, public_id: uuid.UUID, user: User) -> TaskAttempt | None:
    return db.scalar(select(TaskAttempt).where(
        TaskAttempt.public_id == public_id, TaskAttempt.user_id == user.id
    ))
