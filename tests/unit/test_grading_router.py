import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.user import User
from app.modules.grading import router
from app.modules.grading.sandbox.runner import GradeResult, Verdict
from app.modules.grading.test_cases import TestCase
from app.schemas.task_attempt import CodeTestCreate, TaskAttemptCreate


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


def test_code_test_exposes_the_public_sample_case_but_not_hidden_ones(monkeypatch) -> None:
    """The dry-run test endpoint may show input/actual/expected for the public sample case
    only - it must never leak any other (hidden) test case's input or expected output."""
    sample = TestCase(input="4\n", expected_output="야옹~\n")
    result = GradeResult(Verdict.WRONG_ANSWER, passed=0, total=6, sample_actual="갸우뚱...\n")
    monkeypatch.setattr(router, "run_code_test", lambda *_args, **_kwargs: (result, sample))

    payload = CodeTestCreate(task_public_id=uuid.uuid4(), submitted_code="print('갸우뚱...')")
    response = router.test_code(payload, MagicMock(), User(id=7))

    assert response.verdict == "WRONG_ANSWER"
    assert response.passed == 0
    assert response.total == 6
    assert response.sample_input == "4\n"
    assert response.sample_expected_output == "야옹~\n"
    assert response.sample_actual_output == "갸우뚱...\n"


def test_code_test_without_a_parseable_sample_case_omits_sample_fields(monkeypatch) -> None:
    result = GradeResult(Verdict.SYSTEM_ERROR, passed=0, total=0)
    monkeypatch.setattr(router, "run_code_test", lambda *_args, **_kwargs: (result, None))

    payload = CodeTestCreate(task_public_id=uuid.uuid4(), submitted_code="print(1)")
    response = router.test_code(payload, MagicMock(), User(id=7))

    assert response.sample_input is None
    assert response.sample_expected_output is None
    assert response.sample_actual_output is None
