import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.user import User
from app.modules.grading import router
from app.schemas.task_attempt import TaskAttemptCreate


def _submission(**overrides) -> TaskAttemptCreate:
    values = {
        "request_id": uuid.uuid4(),
        "task_public_id": uuid.uuid4(),
        "presentation_public_id": uuid.uuid4(),
        "selected_option": "D",
        "context_type": "LEARNING",
    }
    values.update(overrides)
    return TaskAttemptCreate.model_validate(values)


def test_learning_multiple_choice_is_graded_immediately(monkeypatch) -> None:
    attempt_id = uuid.uuid4()
    monkeypatch.setattr(router, "create_attempt", lambda *_: SimpleNamespace(public_id=attempt_id))
    grade = MagicMock()
    monkeypatch.setattr(router, "grade_attempt", grade)

    result = router.submit(_submission(), MagicMock(), User(id=7))

    assert result.public_id == attempt_id
    grade.assert_called_once_with(attempt_id)


def test_learning_code_submission_stays_on_worker_queue(monkeypatch) -> None:
    attempt_id = uuid.uuid4()
    monkeypatch.setattr(router, "create_attempt", lambda *_: SimpleNamespace(public_id=attempt_id))
    grade = MagicMock()
    monkeypatch.setattr(router, "grade_attempt", grade)

    router.submit(
        _submission(presentation_public_id=None, selected_option=None, submitted_code="print(6)"),
        MagicMock(),
        User(id=7),
    )

    grade.assert_not_called()
