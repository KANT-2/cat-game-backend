import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.main import app
from app.schemas.task import to_task_read
from app.schemas.task_attempt import to_task_attempt_read


def test_part2_get_responses_have_explicit_openapi_schemas():
    paths = app.openapi()["paths"]
    for path in (
        "/api/v1/attempts/{attempt_public_id}",
        "/api/v1/learning/recommendations",
        "/api/v1/learning/weak-concepts",
    ):
        schema = paths[path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema != {}


def test_task_converter_exposes_only_public_relationship_ids():
    task = SimpleNamespace(
        id=12, public_id=uuid.uuid4(), concept_id=3, title="SQL select", type="CODE",
        domain="SQL", difficulty="BRONZE", description="desc", template_code="SELECT ",
        options=None, hint_text=None, is_active=True, test_cases="secret",
    )
    concept = SimpleNamespace(id=3, public_id=uuid.uuid4())
    payload = to_task_read(task, concept).model_dump()
    assert payload["concept_public_id"] == concept.public_id
    assert "id" not in payload and "concept_id" not in payload and "test_cases" not in payload


def test_attempt_converter_does_not_expose_internal_ids_or_submission():
    attempt = SimpleNamespace(
        id=20, public_id=uuid.uuid4(), task_id=12, user_id=7, context_type="LEARNING",
        submitted_code="SELECT secret", status="COMPLETED", is_correct=True,
        used_hint=False, attempted_at=datetime.now(UTC), result_detail=None,
    )
    task = SimpleNamespace(id=12, public_id=uuid.uuid4())
    payload = to_task_attempt_read(attempt, task).model_dump()
    assert payload["task_public_id"] == task.public_id
    assert "id" not in payload and "task_id" not in payload and "user_id" not in payload
    assert "submitted_code" not in payload
