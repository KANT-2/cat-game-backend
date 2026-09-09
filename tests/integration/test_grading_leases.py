import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.core.config import settings
from app.modules.grading.sandbox.runner import GradeResult, Verdict
from app.modules.grading.service import AttemptLease, claim_attempt, grade_claimed_attempt


class AcceptedRunner:
    def grade(self, _task, _submission):
        return GradeResult(Verdict.ACCEPTED, passed=1, total=1)


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
                text("DELETE FROM task_attempts WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            connection.execute(text("DELETE FROM tasks WHERE id = :task_id"), {"task_id": task_id})
            connection.execute(
                text("DELETE FROM concepts WHERE id = :concept_id"),
                {"concept_id": concept_id},
            )
            connection.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
