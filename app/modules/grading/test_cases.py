import json
from dataclasses import dataclass


class TestCaseSpecError(ValueError):
    pass


@dataclass(frozen=True)
class TestCase:
    input: str
    expected_output: str


def parse_test_cases(raw: str) -> list[TestCase]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TestCaseSpecError("test_cases is not valid JSON") from exc
    if not isinstance(value, list) or not value:
        raise TestCaseSpecError("test_cases must be a non-empty JSON array")
    parsed = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != {"input", "expected_output"}:
            raise TestCaseSpecError(
                f"test_cases[{index}] must contain only input and expected_output"
            )
        if not isinstance(item["input"], str) or not isinstance(item["expected_output"], str):
            raise TestCaseSpecError(f"test_cases[{index}] values must be strings")
        parsed.append(TestCase(**item))
    return parsed
