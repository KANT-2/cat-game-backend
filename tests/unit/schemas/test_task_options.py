import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.schemas.task import to_task_read


def test_public_multiple_choice_options_are_shuffled_without_changing_ids() -> None:
    task = SimpleNamespace(
        public_id=uuid.uuid4(),
        title="쉬운 객관식",
        type="MULTIPLE_CHOICE",
        difficulty="BRONZE",
        description="가장 알맞은 방법을 고르세요.",
        template_code="",
        options={"A": "정답", "B": "오답 1", "C": "오답 2", "D": "오답 3"},
        hint_text="작은 예시를 생각하세요.",
        is_active=True,
        reward_coins=30,
    )
    concept = SimpleNamespace(public_id=uuid.uuid4(), domain="PYTHON", name="basics")

    with patch("app.schemas.task.SystemRandom") as random_type:
        random_type.return_value.shuffle.side_effect = lambda values: values.reverse()
        result = to_task_read(task, concept)

    assert list(result.options or {}) == ["D", "C", "B", "A"]
    assert result.options == {"D": "오답 3", "C": "오답 2", "B": "오답 1", "A": "정답"}
