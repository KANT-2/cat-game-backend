import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.grading.runners import (
    MultipleChoiceRunner,
    PythonSandboxRunner,
    RunnerDispatcher,
    Verdict,
)
from app.modules.learning.proficiency import ConceptAssessment, calculate_proficiency
from app.schemas.task import TaskRead
from app.schemas.task_attempt import TaskAttemptCreate
from scripts.seed_learning_tasks import build_tasks
from scripts.seed_sql_tasks import build_tasks as build_sql_tasks


def submission(**values):
    data = {"task_public_id": uuid.uuid4(), "context_type": "LEARNING"}
    data.update(values)
    return TaskAttemptCreate.model_validate(data)


def test_submission_requires_exactly_one_answer_shape():
    submission(submitted_code="print(1)")
    submission(selected_option="A")
    with pytest.raises(ValidationError): submission()
    with pytest.raises(ValidationError): submission(submitted_code="x", selected_option="A")


def test_multiple_choice_is_graded_without_python_sandbox():
    task = SimpleNamespace(type="MULTIPLE_CHOICE", domain="PYTHON", correct_option="B")
    runner = RunnerDispatcher().for_task(task)
    assert isinstance(runner, MultipleChoiceRunner)
    assert runner.grade(task, "B").verdict is Verdict.ACCEPTED
    assert runner.grade(task, "A").verdict is Verdict.WRONG_ANSWER


def test_python_code_tasks_keep_using_the_sandbox():
    task = SimpleNamespace(type="CODE", domain="PYTHON")
    assert isinstance(RunnerDispatcher().for_task(task), PythonSandboxRunner)


def test_proficiency_and_weakness_policy():
    assert calculate_proficiency([True, False, False, True]) == 50
    assert ConceptAssessment(1, 2, 0).is_weak is False
    assert ConceptAssessment(1, 3, 33).is_weak is True
    assert ConceptAssessment(1, 3, 67).is_weak is False


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
