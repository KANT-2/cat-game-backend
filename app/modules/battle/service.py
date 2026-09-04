import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.room import Room
from app.models.room_participant import RoomParticipant
from app.models.room_task import RoomTask
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.models.user import User


class BattleError(ValueError):
    pass


def by_public_id(db: Session, model, public_id: uuid.UUID):
    return db.scalar(select(model).where(model.public_id == public_id))


def create_room(db: Session, user: User, title: str, max_participants: int) -> Room:
    room = Room(host_user_id=user.id, title=title, max_participants=max_participants)
    db.add(room)
    db.flush()
    db.add(RoomParticipant(room_id=room.id, user_id=user.id, is_ready=True))
    db.commit()
    db.refresh(room)
    return room


def join_room(db: Session, user: User, room_public_id: uuid.UUID, team_name: str | None) -> Room:
    room = db.scalar(select(Room).where(Room.public_id == room_public_id).with_for_update())
    if room is None or room.status != "WAITING":
        raise BattleError("joinable room not found")
    existing = db.scalar(
        select(RoomParticipant).where(
            RoomParticipant.room_id == room.id, RoomParticipant.user_id == user.id
        )
    )
    if existing is None:
        count = db.scalar(
            select(func.count())
            .select_from(RoomParticipant)
            .where(RoomParticipant.room_id == room.id)
        )
        if count >= room.max_participants:
            raise BattleError("room is full")
        db.add(RoomParticipant(room_id=room.id, user_id=user.id, team_name=team_name))
        db.commit()
    return room


def set_ready(db: Session, user: User, room_public_id: uuid.UUID, ready: bool) -> Room:
    room = by_public_id(db, Room, room_public_id)
    participant = room and db.scalar(
        select(RoomParticipant).where(
            RoomParticipant.room_id == room.id, RoomParticipant.user_id == user.id
        )
    )
    if participant is None or room.status != "WAITING":
        raise BattleError("waiting room participation not found")
    participant.is_ready = ready
    db.commit()
    return room


def start_room(
    db: Session, user: User, room_public_id: uuid.UUID, task_ids: list[uuid.UUID]
) -> Room:
    if settings.battle_correct_score is None:
        raise BattleError("battle scoring policy is not configured")
    room = db.scalar(select(Room).where(Room.public_id == room_public_id).with_for_update())
    if room is None or room.host_user_id != user.id or room.status != "WAITING":
        raise BattleError("host waiting room not found")
    participants = db.scalars(
        select(RoomParticipant).where(RoomParticipant.room_id == room.id)
    ).all()
    if len(participants) < 2 or any(not row.is_ready for row in participants):
        raise BattleError("at least two ready participants are required")
    if not task_ids or len(task_ids) != len(set(task_ids)):
        raise BattleError("provide one or more unique task public IDs")
    tasks = db.scalars(
        select(Task).where(Task.public_id.in_(task_ids), Task.is_active.is_(True))
    ).all()
    indexed = {task.public_id: task for task in tasks}
    if len(indexed) != len(task_ids):
        raise BattleError("active battle task not found")
    for order, task_id in enumerate(task_ids, 1):
        db.add(RoomTask(room_id=room.id, task_id=indexed[task_id].id, task_order=order))
    room.status = "RUNNING"
    db.commit()
    db.refresh(room)
    return room


def room_for_member(db: Session, user: User, room_public_id: uuid.UUID) -> Room:
    room = by_public_id(db, Room, room_public_id)
    member = room and db.scalar(
        select(RoomParticipant.id).where(
            RoomParticipant.room_id == room.id, RoomParticipant.user_id == user.id
        )
    )
    if not member:
        raise BattleError("room not found")
    return room


def finish_if_complete(db: Session, room_id: int) -> None:
    room = db.get(Room, room_id)
    if room is None or room.status != "RUNNING":
        return
    participant_count = db.scalar(
        select(func.count()).select_from(RoomParticipant).where(RoomParticipant.room_id == room_id)
    )
    task_count = db.scalar(
        select(func.count()).select_from(RoomTask).where(RoomTask.room_id == room_id)
    )
    submitted = db.scalar(
        select(
            func.count(
                func.distinct(func.concat(TaskAttempt.user_id, ":", TaskAttempt.room_task_id))
            )
        )
        .select_from(TaskAttempt)
        .join(RoomTask, RoomTask.id == TaskAttempt.room_task_id)
        .where(RoomTask.room_id == room_id, TaskAttempt.status == "COMPLETED")
    )
    if participant_count and task_count and submitted >= participant_count * task_count:
        room.status = "FINISHED"


def record_attempt_result(db: Session, attempt: TaskAttempt) -> None:
    room_task = db.get(RoomTask, attempt.room_task_id)
    if room_task is None:
        raise BattleError("battle task not found")
    if attempt.is_correct and settings.battle_correct_score is not None:
        participant = db.scalar(
            select(RoomParticipant)
            .where(
                RoomParticipant.room_id == room_task.room_id,
                RoomParticipant.user_id == attempt.user_id,
            )
            .with_for_update()
        )
        if participant is None:
            raise BattleError("battle participant not found")
        previous_correct = db.scalar(
            select(TaskAttempt.id).where(
                TaskAttempt.user_id == attempt.user_id,
                TaskAttempt.room_task_id == attempt.room_task_id,
                TaskAttempt.status == "COMPLETED",
                TaskAttempt.is_correct.is_(True),
                TaskAttempt.id != attempt.id,
            )
        )
        if previous_correct is None:
            participant.current_score += settings.battle_correct_score
    db.flush()
    finish_if_complete(db, room_task.room_id)
