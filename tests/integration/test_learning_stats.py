import uuid
from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.time import game_day_bounds, game_today
from app.modules.learning.router import my_daily_stats


def test_my_daily_stats_counts_only_todays_attempts_for_the_caller(engine) -> None:
    day_start, _ = game_day_bounds(game_today())
    yesterday_attempted_at = day_start - timedelta(minutes=1)
    today_attempted_at = day_start + timedelta(minutes=1)
    suffix = uuid.uuid4().hex

    with engine.begin() as connection:
        user_id = connection.execute(
            text(
                "INSERT INTO users (email, username, role, balance, mileage, house_level) "
                "VALUES (:email, :username, 'STUDENT', 0, 0, 1) RETURNING id"
            ),
            {"email": f"daily-stats-{suffix}@example.com", "username": f"stats-{suffix}"},
        ).scalar_one()
        other_user_id = connection.execute(
            text(
                "INSERT INTO users (email, username, role, balance, mileage, house_level) "
                "VALUES (:email, :username, 'STUDENT', 0, 0, 1) RETURNING id"
            ),
            {"email": f"daily-stats-other-{suffix}@example.com", "username": f"stats-other-{suffix}"},
        ).scalar_one()
        concept_id = connection.execute(
            text("INSERT INTO concepts (domain, name) VALUES ('PYTHON', :name) RETURNING id"),
            {"name": f"daily-stats-{suffix}"},
        ).scalar_one()
        task_ids = [
            connection.execute(
                text(
                    "INSERT INTO tasks "
                    "(concept_id, title, type, difficulty, description, template_code, "
                    "test_cases, is_active, reward_coins) VALUES "
                    "(:concept_id, :title, 'CODE', 'BRONZE', 'desc', '', '[]', true, 10) "
                    "RETURNING id"
                ),
                {"concept_id": concept_id, "title": f"daily-stats-{suffix}-{i}"},
            ).scalar_one()
            for i in range(2)
        ]

        def insert_attempt(*, task_id, attempted_at, status, is_correct, used_hint, coins_awarded, for_user=user_id):
            connection.execute(
                text(
                    "INSERT INTO task_attempts "
                    "(user_id, task_id, context_type, submitted_code, status, is_correct, "
                    "used_hint, attempted_at, coins_awarded) VALUES "
                    "(:user_id, :task_id, 'LEARNING', 'print(1)', :status, :is_correct, "
                    ":used_hint, :attempted_at, :coins_awarded)"
                ),
                {
                    "user_id": for_user,
                    "task_id": task_id,
                    "status": status,
                    "is_correct": is_correct,
                    "used_hint": used_hint,
                    "attempted_at": attempted_at,
                    "coins_awarded": coins_awarded,
                },
            )

        # Two attempts today on task 0: one correct-with-hint (rewarded), one incorrect (no reward).
        insert_attempt(
            task_id=task_ids[0], attempted_at=today_attempted_at, status="COMPLETED",
            is_correct=True, used_hint=True, coins_awarded=10,
        )
        insert_attempt(
            task_id=task_ids[0], attempted_at=today_attempted_at, status="COMPLETED",
            is_correct=False, used_hint=False, coins_awarded=0,
        )
        # One attempt today on a different task, still grading (not yet COMPLETED).
        insert_attempt(
            task_id=task_ids[1], attempted_at=today_attempted_at, status="RUNNING",
            is_correct=None, used_hint=False, coins_awarded=0,
        )
        # Noise that must NOT be counted: yesterday's attempt and another user's attempt today.
        insert_attempt(
            task_id=task_ids[0], attempted_at=yesterday_attempted_at, status="COMPLETED",
            is_correct=True, used_hint=False, coins_awarded=10,
        )
        insert_attempt(
            task_id=task_ids[0], attempted_at=today_attempted_at, status="COMPLETED",
            is_correct=True, used_hint=False, coins_awarded=10, for_user=other_user_id,
        )

    with Session(engine) as db:
        result = my_daily_stats(db, SimpleNamespace(id=user_id))

    assert result.game_date == game_today()
    assert result.distinct_tasks_attempted == 2
    assert result.attempts_submitted == 3
    assert result.attempts_completed == 2
    assert result.correct_attempts == 1
    assert result.incorrect_attempts == 1
    assert result.hints_used == 1
    assert result.coins_awarded == 10
