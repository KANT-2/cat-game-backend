from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.models.attendance_task import AttendanceTask
from app.models.concept import Concept
from app.models.room_participant import RoomParticipant
from app.models.room_task import RoomTask
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.models.user import User
from app.modules.battle.service import (
    create_room,
    join_room,
    record_attempt_result,
    set_ready,
    start_room,
)
from app.modules.daily_mission.service import claim_reward, get_or_create_daily


def user(db, name):
    row = User(email=f"{name}@example.com", username=name, role="STUDENT")
    db.add(row)
    db.flush()
    return row


def tasks(db, count=3):
    concept = Concept(name=f"daily-battle-{id(db)}")
    db.add(concept)
    db.flush()
    rows = []
    for number in range(count):
        row = Task(
            concept_id=concept.id,
            title=f"service task {number}",
            type="MULTIPLE_CHOICE",
            domain="PYTHON",
            difficulty="BRONZE",
            description="choose",
            template_code="",
            test_cases="[]",
            options={"A": "yes", "B": "no"},
            correct_option="A",
            is_active=True,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def test_daily_assignment_streak_completion_and_idempotent_reward(db_session, monkeypatch):
    monkeypatch.setattr(settings, "daily_task_count", 3)
    monkeypatch.setattr(settings, "daily_reward_balance", 25)
    current_user = user(db_session, "daily-service")
    tasks(db_session)
    current_date = datetime.now(UTC).date()
    yesterday = get_or_create_daily(db_session, current_user, current_date - timedelta(days=1))
    today = get_or_create_daily(db_session, current_user, current_date)
    assert yesterday.streak_count == 1
    assert today.streak_count == 2
    assigned = db_session.scalars(
        select(AttendanceTask).where(AttendanceTask.attendance_id == today.id)
    ).all()
    assert len(assigned) == 3
    for row in assigned:
        row.is_completed = True
    first = claim_reward(db_session, current_user, today.public_id)
    second = claim_reward(db_session, current_user, today.public_id)
    assert first.daily_reward_claimed_at is not None
    assert second.daily_reward_claimed_at == first.daily_reward_claimed_at
    assert current_user.balance == 25


def test_battle_room_lifecycle_and_finish(db_session, monkeypatch):
    monkeypatch.setattr(settings, "battle_correct_score", 10)
    host = user(db_session, "battle-host")
    guest = user(db_session, "battle-guest")
    selected = tasks(db_session, 2)
    room = create_room(db_session, host, "test battle", 2)
    join_room(db_session, guest, room.public_id, "BLUE")
    set_ready(db_session, guest, room.public_id, True)
    start_room(db_session, host, room.public_id, [task.public_id for task in selected])
    assert room.status == "RUNNING"
    links = db_session.scalars(
        select(RoomTask).where(RoomTask.room_id == room.id).order_by(RoomTask.task_order)
    ).all()
    participants = db_session.scalars(
        select(RoomParticipant).where(RoomParticipant.room_id == room.id)
    ).all()
    for participant in participants:
        for link in links:
            attempt = TaskAttempt(
                user_id=participant.user_id,
                task_id=link.task_id,
                room_task_id=link.id,
                context_type="BATTLE",
                submitted_code="A",
                status="COMPLETED",
                is_correct=True,
                used_hint=False,
            )
            db_session.add(attempt)
            db_session.flush()
            record_attempt_result(db_session, attempt)
    assert room.status == "FINISHED"
    assert {participant.current_score for participant in participants} == {20}
