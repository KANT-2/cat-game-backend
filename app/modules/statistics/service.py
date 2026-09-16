import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.game_activity_event import GameActivityEvent
from app.models.user import User

GAME_ENTERED = "GAME_ENTERED"


def record_game_entry(db: Session, user: User) -> None:
    """Append one successful game dashboard entry without copying personal payload data."""
    db.add(GameActivityEvent(user_id=user.id, event_type=GAME_ENTERED))
    db.commit()


def daily_game_statistics(db: Session, date_from: date, date_to: date) -> list[dict]:
    rows = db.execute(
        text(
            "SELECT game_date, daily_active_users, game_entries, active_learners, "
            "attempts_submitted, attempts_completed, correct_attempts, incorrect_attempts, "
            "grading_failed_attempts, hints_used, coins_awarded "
            "FROM analytics_daily_game_statistics "
            "WHERE game_date BETWEEN :date_from AND :date_to ORDER BY game_date"
        ),
        {"date_from": date_from, "date_to": date_to},
    )
    return [dict(row._mapping) for row in rows]


def user_daily_learning_statistics(db: Session, date_from: date, date_to: date) -> list[dict]:
    rows = db.execute(
        text(
            "SELECT game_date, user_public_id, username, distinct_tasks_attempted, "
            "attempts_submitted, attempts_completed, correct_attempts, incorrect_attempts, "
            "grading_failed_attempts, hints_used, coins_awarded "
            "FROM analytics_user_daily_learning_statistics "
            "WHERE game_date BETWEEN :date_from AND :date_to "
            "ORDER BY game_date, username, user_public_id"
        ),
        {"date_from": date_from, "date_to": date_to},
    )
    return [dict(row._mapping) for row in rows]


def user_daily_learning_statistics_for_user(
    db: Session, user_public_id: uuid.UUID, date_from: date, date_to: date
) -> list[dict]:
    rows = db.execute(
        text(
            "SELECT game_date, distinct_tasks_attempted, "
            "attempts_submitted, attempts_completed, correct_attempts, incorrect_attempts, "
            "grading_failed_attempts, hints_used, coins_awarded "
            "FROM analytics_user_daily_learning_statistics "
            "WHERE user_public_id = :user_public_id AND game_date BETWEEN :date_from AND :date_to "
            "ORDER BY game_date"
        ),
        {"user_public_id": user_public_id, "date_from": date_from, "date_to": date_to},
    )
    return [dict(row._mapping) for row in rows]
