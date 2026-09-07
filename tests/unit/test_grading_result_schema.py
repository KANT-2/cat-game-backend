import uuid
from datetime import UTC, datetime

from app.modules.grading.router import _read_public_result
from app.schemas.task_attempt import TaskAttemptRead


def test_attempt_result_contract_excludes_submission_and_internal_detail() -> None:
    result = _read_public_result(
        '{"verdict":"RUNTIME_ERROR","passed":1,"total":2,"detail":"secret stderr"}'
    )
    payload = TaskAttemptRead(
        public_id=uuid.uuid4(),
        task_public_id=uuid.uuid4(),
        context_type="LEARNING",
        status="COMPLETED",
        is_correct=False,
        used_hint=False,
        attempted_at=datetime.now(UTC),
        result_detail=result,
        coins_awarded=0,
    ).model_dump(mode="json")

    assert payload["result_detail"] == {
        "verdict": "RUNTIME_ERROR",
        "passed": 1,
        "total": 2,
    }
    assert "submitted_code" not in payload


def test_invalid_stored_result_degrades_to_safe_system_error() -> None:
    result = _read_public_result("not-json")

    assert result is not None
    assert result.model_dump() == {"verdict": "SYSTEM_ERROR", "passed": 0, "total": 0}
