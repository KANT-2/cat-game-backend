from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attendance import Attendance
from app.models.attendance_task import AttendanceTask
from app.models.task import Task
from app.models.user import User
from app.modules.learning.proficiency import recommended_tasks


class DailyMissionError(ValueError):
    pass


def get_or_create_daily(db: Session, user: User, today: date) -> Attendance:
    attendance = db.scalar(
        select(Attendance).where(Attendance.user_id == user.id, Attendance.check_in_date == today)
    )
    if attendance is not None:
        return attendance
    previous = db.scalar(
        select(Attendance).where(
            Attendance.user_id == user.id, Attendance.check_in_date == today - timedelta(days=1)
        )
    )
    attendance = Attendance(
        user_id=user.id,
        check_in_date=today,
        streak_count=(previous.streak_count + 1) if previous else 1,
    )
    db.add(attendance)
    db.flush()
    tasks = recommended_tasks(db, user.id, settings.daily_task_count)
    if len(tasks) < settings.daily_task_count:
        raise DailyMissionError("not enough active tasks to assign the daily mission")
    for order, task in enumerate(tasks, 1):
        db.add(AttendanceTask(attendance_id=attendance.id, task_id=task.id, task_order=order))
    db.commit()
    db.refresh(attendance)
    return attendance


def daily_tasks(db: Session, attendance: Attendance) -> list[tuple[AttendanceTask, Task]]:
    return list(
        db.execute(
            select(AttendanceTask, Task)
            .join(Task, Task.id == AttendanceTask.task_id)
            .where(AttendanceTask.attendance_id == attendance.id)
            .order_by(AttendanceTask.task_order)
        ).all()
    )


def claim_reward(db: Session, user: User, attendance_public_id) -> Attendance:
    if settings.daily_reward_balance is None:
        raise DailyMissionError("daily reward policy is not configured")
    attendance = db.scalar(
        select(Attendance)
        .where(
            Attendance.public_id == attendance_public_id,
            Attendance.user_id == user.id,
        )
        .with_for_update()
    )
    if attendance is None:
        raise DailyMissionError("daily mission not found")
    if attendance.daily_reward_claimed_at is not None:
        return attendance
    tasks = db.scalars(
        select(AttendanceTask).where(AttendanceTask.attendance_id == attendance.id)
    ).all()
    if not tasks or any(not task.is_completed for task in tasks):
        raise DailyMissionError("daily mission is not complete")
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    locked_user.balance += settings.daily_reward_balance
    attendance.daily_reward_claimed_at = datetime.now(UTC)
    db.commit()
    db.refresh(attendance)
    return attendance
