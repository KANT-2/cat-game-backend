import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.core.config import settings
from app.core.time import game_date_at, game_day_bounds, game_today
from app.modules.grading.sandbox.runner import GradeResult, Verdict
from app.modules.grading.service import AttemptLease, claim_attempt, grade_claimed_attempt


class AcceptedRunner:
    def grade(self, _task, _submission):
        return GradeResult(Verdict.ACCEPTED, passed=1, total=1)


def test_task_reward_is_granted_again_on_the_next_game_date(engine) -> None:
    day_start, _ = game_day_bounds(game_today())
    previous_attempted_at = day_start - timedelta(minutes=1)
    today_attempted_at = day_start + timedelta(minutes=1)
    suffix = uuid.uuid4().hex

    with engine.begin() as connection:
        user_id = connection.execute(
            text(
                "INSERT INTO users (email, username, role, balance, mileage, house_level) "
                "VALUES (:email, :username, 'STUDENT', 25, 0, 1) RETURNING id"
            ),
            {"email": f"daily-task-reward-{suffix}@example.com", "username": f"reward-{suffix}"},
        ).scalar_one()
        concept_id = connection.execute(
            text("INSERT INTO concepts (domain, name) VALUES ('PYTHON', :name) RETURNING id"),
            {"name": f"daily-task-reward-{suffix}"},
        ).scalar_one()
        task_id = connection.execute(
            text(
                "INSERT INTO tasks "
                "(concept_id, title, type, difficulty, description, template_code, "
                "test_cases, is_active, reward_coins) VALUES "
                "(:concept_id, 'daily reward task', 'CODE', 'BRONZE', 'desc', '', "
                "'[]', true, 25) RETURNING id"
            ),
            {"concept_id": concept_id},
        ).scalar_one()
        previous_attempt_id = connection.execute(
            text(
                "INSERT INTO task_attempts "
                "(user_id, task_id, context_type, submitted_code, status, is_correct, "
                "used_hint, attempted_at, coins_awarded) VALUES "
                "(:user_id, :task_id, 'LEARNING', 'print(1)', 'COMPLETED', true, "
                "false, :attempted_at, 25) RETURNING id"
            ),
            {
                "user_id": user_id,
                "task_id": task_id,
                "attempted_at": previous_attempted_at,
            },
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO task_completions "
                "(user_id, task_id, first_attempt_id, coins_awarded, completion_date, completed_at) "
                "VALUES (:user_id, :task_id, :attempt_id, 25, :completion_date, :completed_at)"
            ),
            {
                "user_id": user_id,
                "task_id": task_id,
                "attempt_id": previous_attempt_id,
                "completion_date": game_date_at(previous_attempted_at),
                "completed_at": previous_attempted_at,
            },
        )
        leases = []
        for offset in range(2):
            token = uuid.uuid4()
            attempt_public_id = connection.execute(
                text(
                    "INSERT INTO task_attempts "
                    "(user_id, task_id, context_type, submitted_code, status, used_hint, "
                    "attempted_at, grading_started_at, grading_lease_token) VALUES "
                    "(:user_id, :task_id, 'LEARNING', 'print(1)', 'RUNNING', false, "
                    ":attempted_at, :started_at, :token) RETURNING public_id"
                ),
                {
                    "user_id": user_id,
                    "task_id": task_id,
                    "attempted_at": today_attempted_at + timedelta(seconds=offset),
                    "started_at": datetime.now(UTC),
                    "token": token,
                },
            ).scalar_one()
            leases.append(AttemptLease(public_id=attempt_public_id, token=token))

    try:
        assert grade_claimed_attempt(leases[0], AcceptedRunner())
        assert grade_claimed_attempt(leases[1], AcceptedRunner())

        with engine.connect() as connection:
            awarded = connection.execute(
                text(
                    "SELECT coins_awarded FROM task_attempts "
                    "WHERE user_id = :user_id AND attempted_at >= :day_start "
                    "ORDER BY attempted_at, id"
                ),
                {"user_id": user_id, "day_start": day_start},
            ).scalars().all()
            balance = connection.execute(
                text("SELECT balance FROM users WHERE id = :user_id"),
                {"user_id": user_id},
            ).scalar_one()
            reward_dates = connection.execute(
                text(
                    "SELECT completion_date FROM task_completions "
                    "WHERE user_id = :user_id ORDER BY completion_date"
                ),
                {"user_id": user_id},
            ).scalars().all()

        assert awarded == [25, 0]
        assert balance == 50
        assert reward_dates == [game_date_at(previous_attempted_at), game_date_at(today_attempted_at)]
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM task_completions WHERE user_id = :user_id"), {"user_id": user_id})
            connection.execute(text("DELETE FROM user_proficiency WHERE user_id = :user_id"), {"user_id": user_id})
            connection.execute(text("DELETE FROM user_learning_tiers WHERE user_id = :user_id"), {"user_id": user_id})
            connection.execute(text("DELETE FROM task_attempts WHERE user_id = :user_id"), {"user_id": user_id})
            connection.execute(text("DELETE FROM tasks WHERE id = :task_id"), {"task_id": task_id})
            connection.execute(text("DELETE FROM concepts WHERE id = :concept_id"), {"concept_id": concept_id})
            connection.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})


def test_expired_attempt_is_released_without_accepting_stale_result(engine) -> None:
    now = datetime.now(UTC)
    old_token = uuid.uuid4()
    suffix = uuid.uuid4().hex

    with engine.begin() as connection:
        user_id = connection.execute(
            text(
                "INSERT INTO users (email, username, role, balance, mileage, house_level) "
                "VALUES (:email, :username, 'STUDENT', 0, 0, 1) RETURNING id"
            ),
            {"email": f"grading-lease-{suffix}@example.com", "username": f"lease-{suffix}"},
        ).scalar_one()
        concept_id = connection.execute(
            text("INSERT INTO concepts (domain, name) VALUES ('PYTHON', :name) RETURNING id"),
            {"name": f"grading-lease-{suffix}"},
        ).scalar_one()
        task_id = connection.execute(
            text(
                "INSERT INTO tasks "
                "(concept_id, title, type, difficulty, description, template_code, "
                "test_cases, is_active, reward_coins) VALUES "
                "(:concept_id, 'lease task', 'CODE', 'BRONZE', 'desc', '', "
                "'[]', true, 0) RETURNING id"
            ),
            {"concept_id": concept_id},
        ).scalar_one()
        attempt_public_id = connection.execute(
            text(
                "INSERT INTO task_attempts "
                "(user_id, task_id, context_type, submitted_code, status, used_hint, "
                "grading_started_at, grading_lease_token) VALUES "
                "(:user_id, :task_id, 'LEARNING', 'print(1)', 'RUNNING', false, "
                ":started_at, :token) RETURNING public_id"
            ),
            {
                "user_id": user_id,
                "task_id": task_id,
                "started_at": now - timedelta(seconds=settings.grading_lease_seconds + 1),
                "token": old_token,
            },
        ).scalar_one()

    try:
        replacement = claim_attempt(attempt_public_id, now=now)

        assert replacement is not None
        assert replacement.token != old_token
        assert not grade_claimed_attempt(
            AttemptLease(public_id=attempt_public_id, token=old_token), AcceptedRunner()
        )
        assert grade_claimed_attempt(replacement, AcceptedRunner())

        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT status, is_correct, result_detail, grading_started_at, "
                    "grading_lease_token FROM task_attempts WHERE public_id = :public_id"
                ),
                {"public_id": attempt_public_id},
            ).one()
        assert row.status == "COMPLETED"
        assert row.is_correct is True
        assert json.loads(row.result_detail) == {
            "verdict": "ACCEPTED",
            "passed": 1,
            "total": 1,
        }
        assert row.grading_started_at is None
        assert row.grading_lease_token is None
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM task_completions WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            connection.execute(
                text("DELETE FROM user_proficiency WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            connection.execute(
                text("DELETE FROM user_learning_tiers WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            connection.execute(
                text("DELETE FROM task_attempts WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            connection.execute(text("DELETE FROM tasks WHERE id = :task_id"), {"task_id": task_id})
            connection.execute(
                text("DELETE FROM concepts WHERE id = :concept_id"),
                {"concept_id": concept_id},
            )
            connection.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
