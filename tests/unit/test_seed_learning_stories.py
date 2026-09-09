"""Keep the 300 seed grading contracts unchanged while refreshing story copy."""

import hashlib
import json
from collections import Counter

import pytest

from scripts import seed_learning_tasks as python_seed
from scripts import seed_sql_tasks as sql_seed


@pytest.mark.parametrize(
    ("seed", "digest"),
    [
        (python_seed, "eebcde2f1b864fa0a2a6b3265f28b850057610b574831b1361502fd3b1a3efc3"),
        (sql_seed, "d31b71c617a1ced13eb220a17b0c2c422df3800876d3bf9ce7397d19af690222"),
    ],
)
def test_story_refresh_preserves_main_grading_contract(seed, digest):
    rows = seed.build_tasks()
    assert len(rows) == len({seed.seed_key(row["title"]) for row in rows}) == 150
    assert Counter(row["difficulty"] for row in rows) == {"BRONZE": 50, "SILVER": 50, "GOLD": 50}
    data = [
        {k: v for k, v in row.items() if k not in ("title", "description")}
        | {"key": seed.seed_key(row["title"])}
        for row in rows
    ]
    # Golden digest from main covers every template, test case, option, answer,
    # concept, difficulty, reward and stable seed key, excluding only prose.
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
