import json
import subprocess
import sys
from pathlib import Path

import pytest

RUNNER = Path(__file__).parents[2] / "infra" / "docker" / "grader" / "runner.py"


def run(code, expected="ok"):
    payload = json.dumps(
        {
            "code": code,
            "test_cases": [{"input": "ok\n", "expected_output": expected + "\n"}],
        }
    )
    completed = subprocess.run(
        [sys.executable, str(RUNNER)],
        input=payload,
        text=True,
        capture_output=True,
        timeout=4,
        check=True,
    )
    return json.loads(completed.stdout)


@pytest.mark.parametrize(
    ("code", "verdict"),
    [
        ("print(input())", "ACCEPTED"),
        ("print('wrong')", "WRONG_ANSWER"),
        ("print(", "SYNTAX_ERROR"),
        ("raise RuntimeError('boom')", "RUNTIME_ERROR"),
        ("while True: pass", "TIMEOUT"),
    ],
)
def test_runtime_verdicts(code, verdict):
    assert run(code)["verdict"] == verdict
