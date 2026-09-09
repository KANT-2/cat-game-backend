import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import IdempotencyConflictError
from app.core.request_hash import build_request_hash
from app.db.session import SessionLocal
from app.models.attendance import Attendance
from app.models.attendance_task import AttendanceTask
from app.models.room import Room
from app.models.room_participant import RoomParticipant
from app.models.room_task import RoomTask
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.models.task_completion import TaskCompletion
from app.models.user import User
from app.modules.battle.service import record_attempt_result
from app.modules.grading.runners import TaskRunner, dispatcher
from app.modules.grading.sandbox.runner import GradeResult, Verdict
from app.modules.grading.test_cases import TestCaseSpecError
from app.modules.learning.proficiency import update_proficiency
from app.schemas.task_attempt import TaskAttemptCreate

logger = logging.getLogger(__name__)
_OPERATION_TYPE = "TASK_ATTEMPT"


class SubmissionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AttemptLease:
    """Public attempt identifier and opaque lease required to persist one grading result."""

    public_id: uuid.UUID
    token: uuid.UUID


def _by_public_id(db: Session, model, public_id: uuid.UUID):
    return db.scalar(select(model).where(model.public_id == public_id))


def create_attempt(db: Session, payload: TaskAttemptCreate, user: User) -> TaskAttempt:
    request_hash = build_request_hash(
        operation_type=_OPERATION_TYPE,
        payload=payload.model_dump(),
    )
    existing = db.scalar(select(TaskAttempt).where(TaskAttempt.request_id == payload.request_id))
    if existing is not None:
        return _replay_attempt(existing, user.id, request_hash)

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
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise SubmissionError("user not found")

    existing = db.scalar(select(TaskAttempt).where(TaskAttempt.request_id == payload.request_id))
    if existing is not None:
        return _replay_attempt(existing, user.id, request_hash)

    attempt_id = db.scalar(
        insert(TaskAttempt)
        .values(
            request_id=payload.request_id,
            request_hash=request_hash,
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
        .on_conflict_do_nothing(index_elements=[TaskAttempt.request_id])
        .returning(TaskAttempt.id)
    )
    if attempt_id is None:
        existing = db.scalar(select(TaskAttempt).where(TaskAttempt.request_id == payload.request_id))
        if existing is None:
            raise RuntimeError("idempotent attempt insert conflict could not be read")
        return _replay_attempt(existing, user.id, request_hash)

    locked_user.advance_state_version()
    db.commit()
    attempt = db.get(TaskAttempt, attempt_id)
    if attempt is None:
        raise RuntimeError("created attempt could not be read")
    db.refresh(attempt)
    return attempt


def _replay_attempt(existing: TaskAttempt, user_id: int, request_hash: str) -> TaskAttempt:
    if existing.user_id != user_id or existing.request_hash != request_hash:
        raise IdempotencyConflictError("request_id conflict")
    return existing


def claim_next_attempt(now: datetime | None = None) -> AttemptLease | None:
    """Atomically lease the oldest pending or expired-running attempt for one worker."""
    db = SessionLocal()
    try:
        claimed_at = now or datetime.now(UTC)
        attempt = db.scalar(
            select(TaskAttempt)
            .where(_claimable_at(claimed_at))
            .order_by(TaskAttempt.attempted_at, TaskAttempt.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if attempt is None:
            return None
        return _lease(db, attempt, claimed_at)
    finally:
        db.close()


def claim_attempt(attempt_public_id: uuid.UUID, now: datetime | None = None) -> AttemptLease | None:
    """Lease one specific pending or expired-running attempt for maintenance."""
    db = SessionLocal()
    try:
        claimed_at = now or datetime.now(UTC)
        attempt = db.scalar(
            select(TaskAttempt)
            .where(TaskAttempt.public_id == attempt_public_id, _claimable_at(claimed_at))
            .with_for_update()
        )
        if attempt is None:
            return None
        return _lease(db, attempt, claimed_at)
    finally:
        db.close()


def _claimable_at(claimed_at: datetime):
    expired_before = claimed_at - timedelta(seconds=settings.grading_lease_seconds)
    return or_(
        TaskAttempt.status == "PENDING",
        and_(
            TaskAttempt.status == "RUNNING",
            or_(
                TaskAttempt.grading_started_at.is_(None),
                TaskAttempt.grading_started_at < expired_before,
            ),
        ),
    )


def _lease(db: Session, attempt: TaskAttempt, claimed_at: datetime) -> AttemptLease:
    token = uuid.uuid4()
    attempt.status = "RUNNING"
    attempt.grading_started_at = claimed_at
    attempt.grading_lease_token = token
    db.commit()
    return AttemptLease(public_id=attempt.public_id, token=token)


def grade_claimed_attempt(lease: AttemptLease, runner: TaskRunner | None = None) -> bool:
    """Grade one leased attempt and persist a result only while its lease remains current."""
    db = SessionLocal()
    try:
        attempt = db.scalar(
            select(TaskAttempt).where(
                TaskAttempt.public_id == lease.public_id,
                TaskAttempt.status == "RUNNING",
                TaskAttempt.grading_lease_token == lease.token,
            )
        )
        if attempt is None:
            return False
        task = db.get(Task, attempt.task_id)
        if task is None:
            grade_result = GradeResult(Verdict.SYSTEM_ERROR)
        else:
            grade_result = _run_safely(lease.public_id, runner, task, attempt)
        return _persist_result(db, lease, task, grade_result)
    except Exception:  # noqa: BLE001 - an expired lease is retried by a worker
        db.rollback()
        logger.error("grading result persistence failed for attempt %s", lease.public_id)
        return False
    finally:
        db.close()


def _run_safely(
    attempt_public_id: uuid.UUID,
    runner: TaskRunner | None,
    task: Task,
    attempt: TaskAttempt,
) -> GradeResult:
    try:
        return (runner or dispatcher.for_task(task)).grade(task, attempt.submitted_code)
    except TestCaseSpecError:
        return GradeResult(Verdict.SYSTEM_ERROR)
    except Exception:  # noqa: BLE001 - worker boundary converts failures to a safe verdict
        logger.error("grading runner failed for attempt %s", attempt_public_id)
        return GradeResult(Verdict.SYSTEM_ERROR)


def _persist_result(
    db: Session,
    lease: AttemptLease,
    task: Task | None,
    result: GradeResult,
) -> bool:
    db.rollback()
    attempt = db.scalar(
        select(TaskAttempt)
        .where(
            TaskAttempt.public_id == lease.public_id,
            TaskAttempt.status == "RUNNING",
            TaskAttempt.grading_lease_token == lease.token,
        )
        .with_for_update()
    )
    if attempt is None:
        return False
    is_correct = None if result.is_system_failure else result.is_correct
    attempt.status = "FAILED" if result.is_system_failure else "COMPLETED"
    attempt.is_correct = is_correct
    attempt.result_detail = json.dumps(_public_result(result))
    attempt.grading_started_at = None
    attempt.grading_lease_token = None

    locked_user = db.scalar(select(User).where(User.id == attempt.user_id).with_for_update())
    if locked_user is None:
        raise RuntimeError("attempt user not found")
    is_after_reset = False
    if is_correct is not None and task is not None:
        is_after_reset = (
            locked_user.learning_reset_at is None
            or attempt.attempted_at >= locked_user.learning_reset_at
        )
        if is_after_reset:
            update_proficiency(
                db,
                attempt.user_id,
                task.concept_id,
                since=locked_user.learning_reset_at,
            )
    if is_correct and is_after_reset and task is not None:
        completion_id = db.scalar(
            insert(TaskCompletion)
            .values(
                user_id=attempt.user_id,
                task_id=task.id,
                first_attempt_id=attempt.id,
                coins_awarded=task.reward_coins,
            )
            .on_conflict_do_nothing(index_elements=[TaskCompletion.user_id, TaskCompletion.task_id])
            .returning(TaskCompletion.id)
        )
        if completion_id is not None:
            attempt.coins_awarded = task.reward_coins
            locked_user.balance += task.reward_coins
    if is_correct and attempt.context_type == "DAILY":
        attendance_task = db.get(AttendanceTask, attempt.attendance_task_id)
        if attendance_task is None:
            raise RuntimeError("daily attempt attendance task not found")
        attendance_task.is_completed = True
    if attempt.context_type == "BATTLE" and is_correct is not None:
        record_attempt_result(db, attempt)
    locked_user.advance_state_version()
    db.commit()
    return True


def _public_result(result: GradeResult) -> dict[str, str | int]:
    """Return only stable grading fields safe for an authenticated learner response."""
    return {
        "verdict": str(result.verdict),
        "passed": result.passed,
        "total": result.total,
    }


def grade_attempt(attempt_public_id: uuid.UUID) -> None:
    """Synchronously claim and grade one pending or expired attempt for maintenance commands."""
    lease = claim_attempt(attempt_public_id)
    if lease is not None:
        grade_claimed_attempt(lease)


def get_attempt(db: Session, public_id: uuid.UUID, user: User) -> TaskAttempt | None:
    return db.scalar(
        select(TaskAttempt).where(
            TaskAttempt.public_id == public_id,
            TaskAttempt.user_id == user.id,
        )
    )
