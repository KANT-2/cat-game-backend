import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.game.schemas import SettingsCommand
from app.modules.grading.runners import (
    MultipleChoiceRunner,
    PythonSandboxRunner,
    RunnerDispatcher,
    Verdict,
)
from app.modules.learning.proficiency import (
    ConceptAssessment,
    _diversify_daily_tasks,
    calculate_proficiency,
)
from app.modules.learning.router import list_tasks
from app.schemas.task import TaskRead
from app.schemas.task_attempt import TaskAttemptCreate
from scripts.seed_learning_tasks import build_tasks
from scripts.seed_sql_tasks import build_tasks as build_sql_tasks


def submission(**values):
    data = {
        "request_id": uuid.uuid4(),
        "task_public_id": uuid.uuid4(),
        "context_type": "LEARNING",
    }
    data.update(values)
    return TaskAttemptCreate.model_validate(data)


def test_submission_requires_exactly_one_answer_shape():
    submission(submitted_code="print(1)")
    submission(selected_option="A")
    with pytest.raises(ValidationError): submission()
    with pytest.raises(ValidationError): submission(submitted_code="x", selected_option="A")


def test_multiple_choice_is_graded_without_python_sandbox():
    task = SimpleNamespace(type="MULTIPLE_CHOICE", correct_option="B")
    runner = RunnerDispatcher().for_task(task, "PYTHON")
    assert isinstance(runner, MultipleChoiceRunner)
    assert runner.grade(task, "B").verdict is Verdict.ACCEPTED
    assert runner.grade(task, "A").verdict is Verdict.WRONG_ANSWER


def test_python_code_tasks_keep_using_the_sandbox():
    task = SimpleNamespace(type="CODE")
    assert isinstance(RunnerDispatcher().for_task(task, "PYTHON"), PythonSandboxRunner)


def test_proficiency_and_weakness_policy():
    assert calculate_proficiency([True, False, False, True]) == 50
    assert ConceptAssessment(1, 2, 0).is_weak is False
    assert ConceptAssessment(1, 3, 33).is_weak is True
    assert ConceptAssessment(1, 3, 67).is_weak is False


def test_learning_domain_setting_accepts_only_supported_task_domains():
    assert SettingsCommand(learning_domain="SQL").learning_domain == "SQL"
    with pytest.raises(ValidationError):
        SettingsCommand(learning_domain="JAVASCRIPT")


def test_daily_recommendation_balances_concepts_and_changes_daily_order():
    tasks = [
        SimpleNamespace(id=1, concept_id=10, difficulty="BRONZE", type="CODE"),
        SimpleNamespace(id=2, concept_id=10, difficulty="BRONZE", type="MULTIPLE_CHOICE"),
        SimpleNamespace(id=3, concept_id=20, difficulty="BRONZE", type="CODE"),
        SimpleNamespace(id=4, concept_id=20, difficulty="SILVER", type="CODE"),
        SimpleNamespace(id=5, concept_id=30, difficulty="BRONZE", type="MULTIPLE_CHOICE"),
        SimpleNamespace(id=6, concept_id=30, difficulty="GOLD", type="CODE"),
    ]

    first_day = _diversify_daily_tasks(tasks, 7, date(2026, 9, 8), [], 4)
    repeated = _diversify_daily_tasks(tasks, 7, date(2026, 9, 8), [], 4)
    next_day = _diversify_daily_tasks(tasks, 7, date(2026, 9, 9), [], 4)

    assert [task.id for task in first_day] == [task.id for task in repeated]
    assert len({task.concept_id for task in first_day[:3]}) == 3
    assert [task.id for task in first_day] != [task.id for task in next_day]
    assert {task.type for task in first_day} == {"CODE", "MULTIPLE_CHOICE"}


def test_daily_recommendation_keeps_weak_concept_priority_order():
    tasks = [
        SimpleNamespace(id=1, concept_id=10, difficulty="BRONZE", type="CODE"),
        SimpleNamespace(id=2, concept_id=10, difficulty="SILVER", type="CODE"),
        SimpleNamespace(id=3, concept_id=20, difficulty="BRONZE", type="CODE"),
        SimpleNamespace(id=4, concept_id=20, difficulty="SILVER", type="CODE"),
    ]

    selected = _diversify_daily_tasks(tasks, 7, date(2026, 9, 8), [20, 10], 4)

    assert [task.concept_id for task in selected] == [20, 10, 20, 10]
    assert [task.difficulty for task in selected] == ["BRONZE", "BRONZE", "SILVER", "SILVER"]


def test_daily_recommendation_changes_members_when_one_group_has_more_than_limit():
    tasks = [
        SimpleNamespace(id=index, concept_id=10, difficulty="BRONZE", type="CODE")
        for index in range(1, 5)
    ]

    first = _diversify_daily_tasks(tasks, 7, date(2026, 9, 10), [], 3)
    next_day = _diversify_daily_tasks(tasks, 7, date(2026, 9, 11), [], 3)

    assert {task.id for task in first} != {task.id for task in next_day}


@pytest.mark.parametrize("rows", [build_tasks(), build_sql_tasks()])
def test_seeded_recommendation_page_contains_varied_concepts_and_task_types(rows):
    concept_ids = {name: index for index, name in enumerate(sorted({row["concept"] for row in rows}), 1)}
    tasks = [
        SimpleNamespace(
            id=index,
            concept_id=concept_ids[row["concept"]],
            difficulty=row["difficulty"],
            type=row["type"],
        )
        for index, row in enumerate(rows, 1)
    ]

    selected = _diversify_daily_tasks(tasks, 17, date(2026, 9, 10), [], 10)

    assert len({task.concept_id for task in selected}) >= 7
    assert {task.type for task in selected} == {"CODE", "MULTIPLE_CHOICE"}


def test_seed_has_150_balanced_unique_tasks_and_hidden_answers():
    rows = build_tasks()
    assert len(rows) == len({row["title"] for row in rows}) == 150
    assert {level: sum(row["difficulty"] == level for row in rows) for level in ("BRONZE", "SILVER", "GOLD")} == {"BRONZE": 50, "SILVER": 50, "GOLD": 50}
    choices = [row for row in rows if row["type"] == "MULTIPLE_CHOICE"]
    assert choices and all(row["options"] and row["correct_option"] for row in choices)
    assert {row["concept"] for row in rows} == {
        "PYTHON:basics",
        "PYTHON:conditionals",
        "PYTHON:loops",
        "PYTHON:strings",
        "PYTHON:collections",
        "PYTHON:functions",
        "PYTHON:exceptions",
    }


def test_public_task_schema_never_contains_grading_answers():
    assert "correct_option" not in TaskRead.model_fields
    assert "test_cases" not in TaskRead.model_fields
    assert "options" in TaskRead.model_fields
    assert "completed" in TaskRead.model_fields
    assert "concept_name" in TaskRead.model_fields


def test_sql_seed_has_150_balanced_unique_tasks_and_all_concepts():
    rows = build_sql_tasks()
    assert len(rows) == len({row["title"] for row in rows}) == 150
    assert {
        level: sum(row["difficulty"] == level for row in rows)
        for level in ("BRONZE", "SILVER", "GOLD")
    } == {"BRONZE": 50, "SILVER": 50, "GOLD": 50}
    assert {row["concept"] for row in rows} == {
        "SQL:basics", "SQL:filtering", "SQL:aggregation", "SQL:joins",
        "SQL:subqueries", "SQL:advanced_queries", "SQL:data_manipulation",
        "SQL:schema", "SQL:transactions",
    }


class _Rows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _LearningTaskSession:
    def __init__(self, concept, tasks, completed_ids):
        self.concept = concept
        self.tasks = tasks
        self.completed_ids = completed_ids
        self.scalar_statement = None
        self.scalar_statements = []

    def scalar(self, statement):
        self.scalar_statement = statement
        return self.concept

    def scalars(self, statement):
        self.scalar_statements.append(statement)
        if len(self.scalar_statements) == 1:
            return _Rows(self.tasks)
        return _Rows(self.completed_ids)

    def get(self, _model, _identifier):
        return self.concept


def test_learning_task_selection_applies_filters_and_completed_state():
    concept_public_id = uuid.uuid4()
    concept = SimpleNamespace(id=9, public_id=concept_public_id, domain="PYTHON", name="functions")
    task = SimpleNamespace(
        id=21,
        public_id=uuid.uuid4(),
        concept_id=9,
        title="함수 문제",
        type="CODE",
        difficulty="SILVER",
        description="desc",
        template_code="def solve():",
        options=None,
        hint_text=None,
        is_active=True,
        reward_coins=60,
    )
    db = _LearningTaskSession(concept, [task], [task.id])

    response = list_tasks(
        db=db,
        user=SimpleNamespace(id=7, learning_reset_at=None),
        task_type="CODE",
        domain="PYTHON",
        concept_public_id=concept_public_id,
        difficulty="SILVER",
        limit=5,
    )

    assert len(response) == 1
    assert response[0].public_id == task.public_id
    assert response[0].completed is True

    sql = str(db.scalar_statements[0])
    assert "tasks.is_active IS true" in sql
    assert "tasks.type =" in sql
    assert "concepts.domain =" in sql
    assert "tasks.difficulty =" in sql
    assert "tasks.concept_id =" in sql
    assert "ORDER BY tasks.id" in sql
    assert "LIMIT" in sql


def test_learning_task_selection_returns_empty_for_unknown_concept():
    db = _LearningTaskSession(None, [], [])

    response = list_tasks(
        db=db,
        user=SimpleNamespace(id=7),
        concept_public_id=uuid.uuid4(),
        limit=20,
    )

    assert response == []
    assert db.scalar_statements == []
