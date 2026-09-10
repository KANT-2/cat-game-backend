import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.main import app
from app.modules.learning.router import _learning_progress_start, _recommendation_date
from app.schemas.task import to_task_read
from app.schemas.task_attempt import to_task_attempt_read


def test_part2_get_responses_have_explicit_openapi_schemas():
    paths = app.openapi()["paths"]
    for path in (
        "/api/v1/attempts/{attempt_public_id}",
        "/api/v1/learning/tasks",
        "/api/v1/learning/recommendations",
        "/api/v1/learning/proficiencies",
        "/api/v1/learning/weak-concepts",
    ):
        schema = paths[path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema != {}


def test_task_converter_exposes_only_public_relationship_ids():
    task = SimpleNamespace(
        id=12, public_id=uuid.uuid4(), concept_id=3, title="SQL select", type="CODE",
        difficulty="BRONZE", description="desc", template_code="SELECT ",
        options=None, hint_text=None, is_active=True, reward_coins=30, test_cases="secret",
    )
    concept = SimpleNamespace(id=3, public_id=uuid.uuid4(), domain="SQL", name="select")
    payload = to_task_read(task, concept).model_dump()
    assert payload["concept_public_id"] == concept.public_id
    assert payload["domain"] == "SQL"
    assert "id" not in payload and "concept_id" not in payload and "test_cases" not in payload


def test_attempt_converter_does_not_expose_internal_ids_or_submission():
    attempt = SimpleNamespace(
        id=20, public_id=uuid.uuid4(), task_id=12, user_id=7, context_type="LEARNING",
        submitted_code="SELECT secret", status="COMPLETED", is_correct=True,
        used_hint=False, attempted_at=datetime.now(UTC),
        result_detail='{"verdict":"ACCEPTED","detail":null,"passed":3,"total":3}',
        coins_awarded=30,
    )
    task = SimpleNamespace(id=12, public_id=uuid.uuid4())
    payload = to_task_attempt_read(attempt, task).model_dump()
    assert payload["task_public_id"] == task.public_id
    assert "id" not in payload and "task_id" not in payload and "user_id" not in payload
    assert "submitted_code" not in payload
    assert payload["result_detail"] == {
        "verdict": "ACCEPTED",
        "passed": 3,
        "total": 3,
    }


def test_attempt_converter_accepts_legacy_result_detail_shape():
    attempt = SimpleNamespace(
        id=20, public_id=uuid.uuid4(), task_id=12, user_id=7, context_type="LEARNING",
        status="COMPLETED", is_correct=False, used_hint=False, attempted_at=datetime.now(UTC),
        result_detail='{"verdict":"WRONG_ANSWER","detail":"expected 2"}',
        coins_awarded=0,
    )
    task = SimpleNamespace(id=12, public_id=uuid.uuid4())

    payload = to_task_attempt_read(attempt, task).model_dump()

    assert payload["result_detail"] == {
        "verdict": "SYSTEM_ERROR",
        "passed": 0,
        "total": 0,
    }


def test_learning_tasks_openapi_exposes_selection_filters():
    operation = app.openapi()["paths"]["/api/v1/learning/tasks"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert {"type", "domain", "concept_public_id", "difficulty", "limit"} <= set(parameters)
    assert parameters["type"]["schema"]["anyOf"][0]["enum"] == ["CODE", "MULTIPLE_CHOICE"]
    assert parameters["domain"]["schema"]["anyOf"][0]["enum"] == ["PYTHON", "SQL"]
    assert parameters["difficulty"]["schema"]["anyOf"][0]["enum"] == [
        "BRONZE",
        "SILVER",
        "GOLD",
    ]
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50


def test_recommendations_exposes_local_test_date_override():
    operation = app.openapi()["paths"]["/api/v1/learning/recommendations"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert "test_date" in parameters


def test_recommendation_date_override_is_limited_to_local_and_test(monkeypatch):
    selected = date(2026, 9, 9)
    monkeypatch.setattr(settings, "app_env", "local")
    assert _recommendation_date(selected) == selected

    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(HTTPException) as exc_info:
        _recommendation_date(selected)
    assert exc_info.value.status_code == 404


def test_learning_progress_starts_at_game_day_boundary(monkeypatch):
    monkeypatch.setattr("app.modules.learning.router.game_today", lambda: date(2026, 9, 10))

    assert _learning_progress_start(None) == datetime(2026, 9, 9, 15, 0, tzinfo=UTC)


def test_manual_learning_reset_after_day_boundary_takes_precedence(monkeypatch):
    reset_at = datetime(2026, 9, 10, 3, 30, tzinfo=UTC)
    monkeypatch.setattr("app.modules.learning.router.game_today", lambda: date(2026, 9, 10))

    assert _learning_progress_start(reset_at) == reset_at
