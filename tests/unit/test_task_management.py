import uuid
from types import SimpleNamespace

import pytest

from app.modules.tasks.service import deactivate_task, update_task
from app.schemas.task import TaskUpdate


class _TaskManagementSession:
    def __init__(self, task, concept):
        self.task = task
        self.concept = concept
        self.commits = 0

    def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity.__name__ == "Task":
            return self.task
        return self.concept

    def get(self, _model, _identifier):
        return self.concept

    def commit(self):
        self.commits += 1

    def refresh(self, _task):
        pass


def _objects():
    concept = SimpleNamespace(id=7, public_id=uuid.uuid4(), domain="PYTHON", name="loops")
    task = SimpleNamespace(
        public_id=uuid.uuid4(),
        concept_id=concept.id,
        title="반복문",
        type="CODE",
        difficulty="BRONZE",
        description="숫자를 출력하세요.",
        template_code="",
        options=None,
        hint_text=None,
        test_cases="[]",
        correct_option=None,
        is_active=True,
        reward_coins=0,
    )
    return task, concept


def test_update_task_changes_python_or_sql_task_fields() -> None:
    task, concept = _objects()
    db = _TaskManagementSession(task, concept)

    result = update_task(
        db,
        task.public_id,
        TaskUpdate(title="for 반복문", difficulty="SILVER", test_cases=[{"input": "3"}]),
    )

    assert result.title == "for 반복문"
    assert result.domain == "PYTHON"
    assert task.test_cases == '[{"input": "3"}]'
    assert db.commits == 1


def test_update_task_rejects_domain_that_disagrees_with_concept() -> None:
    task, concept = _objects()
    db = _TaskManagementSession(task, concept)

    with pytest.raises(ValueError, match="concept의 domain과 일치"):
        update_task(db, task.public_id, TaskUpdate(domain="SQL"))

    assert db.commits == 0


def test_deactivate_task_preserves_row_and_hides_it_from_learning_queries() -> None:
    task, concept = _objects()
    db = _TaskManagementSession(task, concept)

    deactivate_task(db, task.public_id)

    assert task.is_active is False
    assert db.commits == 1


def test_task_management_returns_not_found_for_unknown_public_id() -> None:
    _task, concept = _objects()
    db = _TaskManagementSession(None, concept)

    with pytest.raises(LookupError, match="존재하지 않는 문제"):
        deactivate_task(db, uuid.uuid4())
