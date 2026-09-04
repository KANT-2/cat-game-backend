import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.attendance import Attendance
from app.models.attendance_task import AttendanceTask
from app.models.room import Room
from app.models.room_participant import RoomParticipant
from app.models.room_task import RoomTask
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.models.user import User
from app.modules.grading.lifecycle import fail_attempt, finish_attempt, mark_running
from app.modules.grading.runners import dispatcher
from app.modules.grading.test_cases import TestCaseSpecError
from app.schemas.task_attempt import TaskAttemptCreate


class SubmissionError(ValueError):
    pass


def _by_public_id(db: Session, model, public_id: uuid.UUID):
    return db.scalar(select(model).where(model.public_id == public_id))


def create_attempt(db: Session, payload: TaskAttemptCreate, user: User) -> TaskAttempt:
    task = _by_public_id(db, Task, payload.task_public_id)
    if task is None or not task.is_active:
        raise SubmissionError("task not found")
    if task.type == "CODE" and payload.submitted_code is None:
        raise SubmissionError("CODE task requires submitted_code")
    if task.type == "MULTIPLE_CHOICE":
        if payload.selected_option is None:
            raise SubmissionError("MULTIPLE_CHOICE task requires selected_option")
        if payload.selected_option not in task.options:
            raise SubmissionError("selected_option is not one of the task options")
    attendance_task = room_task = None
    if payload.context_type == "DAILY":
        attendance_task = _by_public_id(db, AttendanceTask, payload.attendance_task_public_id)
        owned = attendance_task and db.scalar(
            select(Attendance.id).where(
                Attendance.id == attendance_task.attendance_id,
                Attendance.user_id == user.id,
                Attendance.check_in_date == datetime.now(ZoneInfo(settings.game_timezone)).date(),
            )
        )
        if not owned or attendance_task.task_id != task.id or attendance_task.is_completed:
            raise SubmissionError("daily task not found")
    elif payload.context_type == "BATTLE":
        room_task = _by_public_id(db, RoomTask, payload.room_task_public_id)
        participant = room_task and db.scalar(
            select(RoomParticipant.id)
            .join(Room, Room.id == RoomParticipant.room_id)
            .where(
                RoomParticipant.room_id == room_task.room_id,
                RoomParticipant.user_id == user.id,
                Room.status == "RUNNING",
            )
        )
        if not participant or room_task.task_id != task.id:
            raise SubmissionError("battle task not found")
    attempt = TaskAttempt(
        user_id=user.id,
        task_id=task.id,
        attendance_task_id=attendance_task.id if attendance_task else None,
        room_task_id=room_task.id if room_task else None,
        context_type=payload.context_type,
        submitted_code=payload.submitted_code or payload.selected_option,
        used_hint=payload.used_hint,
        status="PENDING",
        is_correct=None,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def grade_attempt(attempt_public_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        attempt = _by_public_id(db, TaskAttempt, attempt_public_id)
        if attempt is None or attempt.status != "PENDING":
            return
        mark_running(db, attempt)
        task = db.get(Task, attempt.task_id)
        try:
            result = dispatcher.for_task(task).grade(task, attempt.submitted_code)
        except TestCaseSpecError as exc:
            fail_attempt(db, attempt, "TEST_CASE_SPEC_ERROR", str(exc))
            return
        finish_attempt(db, attempt, task, result)
    except Exception as exc:  # noqa: BLE001 - background boundary must persist FAILED
        db.rollback()
        attempt = _by_public_id(db, TaskAttempt, attempt_public_id)
        if attempt:
            fail_attempt(db, attempt, "SYSTEM_ERROR", str(exc))
    finally:
        db.close()


def get_attempt(db: Session, public_id: uuid.UUID, user: User) -> TaskAttempt | None:
    return db.scalar(
        select(TaskAttempt).where(
            TaskAttempt.public_id == public_id, TaskAttempt.user_id == user.id
        )
    )
