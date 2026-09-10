"""Keep the 300 seed grading contracts unchanged while refreshing story copy."""

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from scripts import seed_learning_tasks as python_seed
from scripts import seed_sql_tasks as sql_seed


@pytest.mark.parametrize(
    ("seed", "digest"),
    [
        (python_seed, "fa8984fb4f42a20e9764ee5e55cb3294edad1441e7f7fd0518953bb426fb3290"),
        (sql_seed, "77b9e2fe67593a3c9a26f4938093e826633fadf7f21619e98ebabab84ec538ec"),
    ],
)
def test_story_refresh_preserves_main_grading_contract(seed, digest):
    rows = seed.build_tasks()
    assert len(rows) == len({seed.seed_key(row["title"]) for row in rows}) == 150
    assert Counter(row["difficulty"] for row in rows) == {"BRONZE": 50, "SILVER": 50, "GOLD": 50}
    data = [
        {k: v for k, v in row.items() if k not in ("title", "description", "template_code", "hint_text")}
        | {"key": seed.seed_key(row["title"])}
        for row in rows
    ]
    # Golden digest covers every grading case, option, answer, concept, difficulty, reward and
    # stable seed key. Prose, hints and intentionally revised editor starter text are excluded.
    assert (
        hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        == digest
    )
    for row in rows:
        assert "[고양이 이야기]" not in row["description"]
        assert row["description"].count("[도와주세요!]") == 1
        if row["type"] == "MULTIPLE_CHOICE":
            assert row["correct_option"] in row["options"]
    text = " ".join(row["description"] for row in rows)
    for material in ("츄르", "우유", "장난감", "방석", "캣타워", "리본", "목걸이"):
        assert material in text
    assert sum("생선 가게" in row["description"] for row in rows) < 30


def test_python_editor_starts_empty_because_grader_accepts_a_complete_program() -> None:
    tasks = python_seed.build_tasks()
    assert all(row["template_code"] == "" for row in tasks)
    task = next(row for row in tasks if row["type"] == "CODE" and "두 수의 합" in row["title"])
    payload = json.dumps(
        {
            "code": "a, b = map(int, input().split())\nprint(a + b)\n",
            "test_cases": json.loads(task["test_cases"]),
        }
    )
    runner = Path(__file__).parents[2] / "infra" / "docker" / "grader" / "runner.py"
    completed = subprocess.run(
        [sys.executable, str(runner)],
        input=payload,
        text=True,
        capture_output=True,
        timeout=4,
        check=True,
    )
    assert json.loads(completed.stdout)["verdict"] == "ACCEPTED"


def test_sql_editor_uses_only_a_non_solution_comment() -> None:
    code_tasks = [row for row in sql_seed.build_tasks() if row["type"] == "CODE"]
    assert {row["template_code"] for row in code_tasks} == {"-- 아래에 SQL을 작성하세요.\n"}
    assert all(
        keyword not in code_tasks[0]["template_code"].upper()
        for keyword in ("SELECT", "UPDATE", "CREATE")
    )


def test_python_hints_give_operation_specific_next_steps() -> None:
    tasks = python_seed.build_tasks()
    hints = {row["hint_text"] for row in tasks}
    assert len(hints) == 30
    assert "map(int, input().split())" in next(row["hint_text"] for row in tasks if "두 수의 합" in row["title"])
    assert "left와 right" in next(row["hint_text"] for row in tasks if "이진 탐색 위치" in row["title"])
    assert "prefix[r + 1] - prefix[l]" in next(row["hint_text"] for row in tasks if "구간 합 질의" in row["title"])


def test_sql_hints_name_the_clauses_needed_for_each_problem_family() -> None:
    tasks = sql_seed.build_tasks()
    assert len({row["hint_text"] for row in tasks}) >= 12
    assert "WHERE" in next(row["hint_text"] for row in tasks if "학번 1 학생" in row["title"])
    assert "LEFT JOIN" in next(row["hint_text"] for row in tasks if "주문 없는 학생" in row["title"])
    assert "GROUP BY" in next(row["hint_text"] for row in tasks if "팀별 인원" in row["title"])
    assert "dense_rank()" in next(row["hint_text"] for row in tasks if "점수 순위" in row["title"])
    assert "UPDATE students" in next(row["hint_text"] for row in tasks if "점수 수정" in row["title"])
