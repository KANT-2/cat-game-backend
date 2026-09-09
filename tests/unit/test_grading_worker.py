from app.modules.grading.sandbox.runner import GradeResult, Verdict
from app.modules.grading.service import _public_result, _run_safely


class FailingRunner:
    def grade(self, _task, _submission):
        raise RuntimeError("secret infrastructure address")


def test_worker_converts_runner_fault_without_exposing_internal_detail(caplog) -> None:
    result = _run_safely("attempt-public-id", FailingRunner(), object(), "PYTHON", object())

    assert result.verdict is Verdict.SYSTEM_ERROR
    assert "secret infrastructure address" not in caplog.text


def test_public_result_omits_sandbox_and_student_process_details() -> None:
    result = GradeResult(
        Verdict.SYSTEM_ERROR,
        passed=1,
        total=3,
        detail="docker tls secret and raw stderr",
    )

    assert _public_result(result) == {
        "verdict": "SYSTEM_ERROR",
        "passed": 1,
        "total": 3,
    }
