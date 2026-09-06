import json
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.modules.grading.service import claim_attempt, grade_claimed_attempt


def test_daily_attempt_completion_and_result_ownership(engine) -> None:
    suffix = uuid.uuid4().hex
    with engine.begin() as connection:
        owner_id, owner_public_id = connection.execute(
            text(
                "INSERT INTO users (email, username, role, balance, mileage, house_level) "
                "VALUES (:email, :username, 'STUDENT', 0, 0, 1) RETURNING id, public_id"
            ),
            {"email": f"daily-owner-{suffix}@example.com", "username": f"owner-{suffix}"},
        ).one()
        other_id, other_public_id = connection.execute(
            text(
                "INSERT INTO users (email, username, role, balance, mileage, house_level) "
                "VALUES (:email, :username, 'STUDENT', 0, 0, 1) RETURNING id, public_id"
            ),
            {"email": f"daily-other-{suffix}@example.com", "username": f"other-{suffix}"},
        ).one()
        concept_id = connection.execute(
            text("INSERT INTO concepts (name) VALUES (:name) RETURNING id"),
            {"name": f"daily-grading-{suffix}"},
        ).scalar_one()
        task_id, task_public_id = connection.execute(
            text(
                "INSERT INTO tasks "
                "(concept_id, title, type, domain, difficulty, description, template_code, "
                "test_cases, options, correct_option, is_active, reward_coins) VALUES "
                "(:concept_id, 'daily task', 'MULTIPLE_CHOICE', 'PYTHON', 'BRONZE', "
                "'desc', '', '[]', '[\"A\", \"B\"]'::jsonb, 'A', true, 25) "
                "RETURNING id, public_id"
            ),
            {"concept_id": concept_id},
        ).one()
        attendance_id = connection.execute(
            text(
                "INSERT INTO attendances "
                "(user_id, check_in_date, streak_count, daily_reward_claimed_at) "
                "VALUES (:user_id, :today, 1, :claimed_at) RETURNING id"
            ),
            {
                "user_id": owner_id,
                "today": datetime.now(UTC).date(),
                "claimed_at": datetime.now(UTC),
            },
        ).scalar_one()
        attendance_task_public_id = connection.execute(
            text(
                "INSERT INTO attendance_tasks "
                "(attendance_id, task_id, task_order, is_completed) "
                "VALUES (:attendance_id, :task_id, 1, false) RETURNING public_id"
            ),
            {"attendance_id": attendance_id, "task_id": task_id},
        ).scalar_one()

    owner_headers = {"X-User-Public-ID": str(owner_public_id)}
    other_headers = {"X-User-Public-ID": str(other_public_id)}
    try:
        with TestClient(app) as client:
            accepted = client.post(
                "/api/v1/attempts",
                headers=owner_headers,
                json={
                    "task_public_id": str(task_public_id),
                    "selected_option": "A",
                    "context_type": "DAILY",
                    "attendance_task_public_id": str(attendance_task_public_id),
                },
            )
            assert accepted.status_code == 202
            assert accepted.json()["status"] == "PENDING"
            attempt_public_id = uuid.UUID(accepted.json()["public_id"])

            lease = claim_attempt(attempt_public_id)
            assert lease is not None
            assert grade_claimed_attempt(lease)

            result = client.get(f"/api/v1/attempts/{attempt_public_id}", headers=owner_headers)
            hidden = client.get(f"/api/v1/attempts/{attempt_public_id}", headers=other_headers)

        assert result.status_code == 200
        payload = result.json()
        assert payload["task_public_id"] == str(task_public_id)
        assert payload["status"] == "COMPLETED"
        assert payload["is_correct"] is True
        assert payload["coins_awarded"] == 25
        assert json.loads(payload["result_detail"]) == {
            "verdict": "ACCEPTED",
            "passed": 1,
            "total": 1,
        }
        assert "submitted_code" not in payload
        assert hidden.status_code == 404

        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT attendance_tasks.is_completed, users.balance, users.state_version "
                    "FROM attendance_tasks JOIN attendances "
                    "ON attendances.id = attendance_tasks.attendance_id "
                    "JOIN users ON users.id = attendances.user_id "
                    "WHERE attendance_tasks.public_id = :public_id"
                ),
                {"public_id": attendance_task_public_id},
            ).one()
        assert row.is_completed is True
        assert row.balance == 25
        assert row.state_version == 3
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM task_completions WHERE user_id = :user_id"),
                {"user_id": owner_id},
            )
            connection.execute(
                text("DELETE FROM user_proficiency WHERE user_id = :user_id"),
                {"user_id": owner_id},
            )
            connection.execute(
                text("DELETE FROM task_attempts WHERE user_id = :user_id"),
                {"user_id": owner_id},
            )
            connection.execute(
                text("DELETE FROM attendance_tasks WHERE attendance_id = :attendance_id"),
                {"attendance_id": attendance_id},
            )
            connection.execute(
                text("DELETE FROM attendances WHERE id = :attendance_id"),
                {"attendance_id": attendance_id},
            )
            connection.execute(text("DELETE FROM tasks WHERE id = :task_id"), {"task_id": task_id})
            connection.execute(
                text("DELETE FROM concepts WHERE id = :concept_id"),
                {"concept_id": concept_id},
            )
            connection.execute(
                text("DELETE FROM users WHERE id IN (:owner_id, :other_id)"),
                {"owner_id": owner_id, "other_id": other_id},
            )
