import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.models.concept import Concept
from app.models.room_participant import RoomParticipant
from app.models.room_task import RoomTask
from app.models.task import Task
from app.models.user import User
from app.modules.battle.service import (
    BattleError,
    create_room,
    join_room,
    room_for_member,
    set_ready,
    start_room,
)
from app.schemas.battle import (
    BattleRoomRead,
    BattleTaskView,
    ParticipantView,
    ReadyUpdate,
    RoomCreate,
    RoomJoin,
    RoomStart,
)
from app.schemas.task import to_task_read

router = APIRouter(prefix="/battle/rooms", tags=["battle"])


def payload(db, room) -> BattleRoomRead:
    participant_rows = db.execute(
        select(RoomParticipant, User)
        .join(User, User.id == RoomParticipant.user_id)
        .where(RoomParticipant.room_id == room.id)
        .order_by(RoomParticipant.id)
    ).all()
    task_rows = db.execute(
        select(RoomTask, Task)
        .join(Task, Task.id == RoomTask.task_id)
        .where(RoomTask.room_id == room.id)
        .order_by(RoomTask.task_order)
    ).all()
    top = max((link.current_score for link, _ in participant_rows), default=0)
    winners = [
        user.public_id
        for link, user in participant_rows
        if room.status == "FINISHED" and link.current_score == top
    ]
    host = db.get(User, room.host_user_id)
    return BattleRoomRead(
        public_id=room.public_id,
        host_user_public_id=host.public_id,
        title=room.title,
        status=room.status,
        max_participants=room.max_participants,
        participants=[
            ParticipantView(
                user_public_id=user.public_id,
                username=user.username,
                team_name=link.team_name,
                current_score=link.current_score,
                is_ready=link.is_ready,
            )
            for link, user in participant_rows
        ],
        tasks=[
            BattleTaskView(
                room_task_public_id=link.public_id,
                task_order=link.task_order,
                task=to_task_read(task, db.get(Concept, task.concept_id)),
            )
            for link, task in task_rows
        ],
        winner_user_public_ids=winners,
    )


def run(action, db):
    try:
        return action()
    except BattleError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("", response_model=BattleRoomRead, status_code=201)
def create(body: RoomCreate, db: DbSession, user: CurrentUser):
    return payload(db, run(lambda: create_room(db, user, body.title, body.max_participants), db))


@router.get("/{room_public_id}", response_model=BattleRoomRead)
def get(room_public_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return payload(db, run(lambda: room_for_member(db, user, room_public_id), db))


@router.post("/{room_public_id}/join", response_model=BattleRoomRead)
def join(room_public_id: uuid.UUID, body: RoomJoin, db: DbSession, user: CurrentUser):
    return payload(db, run(lambda: join_room(db, user, room_public_id, body.team_name), db))


@router.patch("/{room_public_id}/ready", response_model=BattleRoomRead)
def ready(room_public_id: uuid.UUID, body: ReadyUpdate, db: DbSession, user: CurrentUser):
    return payload(db, run(lambda: set_ready(db, user, room_public_id, body.is_ready), db))


@router.post("/{room_public_id}/start", response_model=BattleRoomRead)
def start(room_public_id: uuid.UUID, body: RoomStart, db: DbSession, user: CurrentUser):
    return payload(db, run(lambda: start_room(db, user, room_public_id, body.task_public_ids), db))
