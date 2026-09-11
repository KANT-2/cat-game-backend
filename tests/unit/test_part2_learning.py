import uuid
from datetime import date
from random import Random
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
from app.modules.grading.service import _run_safely
from app.modules.learning.presentation import (
    choose_presentation_type,
    shuffled_options,
    start_task_presentation,
)
from app.modules.learning.proficiency import (
    ConceptAssessment,
    _diversify_daily_tasks,
    _task_problem_key,
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


def test_persisted_multiple_choice_presentation_uses_its_stored_answer():
    class RunnerThatMustNotRun:
        def grade(self, _task, _submission):
            raise AssertionError("multiple-choice presentation must bypass direct grading")

    result = _run_safely(
        uuid.uuid4(),
        RunnerThatMustNotRun(),
        SimpleNamespace(type="CODE"),
        "SQL",
        SimpleNamespace(submitted_code="C"),
        SimpleNamespace(presentation_type="MULTIPLE_CHOICE", correct_option="C"),
    )

    assert result.verdict is Verdict.ACCEPTED


@pytest.mark.parametrize(
    ("difficulty", "expected", "tolerance"),
    [("BRONZE", 0.5, 0.03), ("SILVER", 0.2, 0.03), ("GOLD", 0.0, 0.0)],
)
@pytest.mark.parametrize("domain", ["PYTHON", "SQL"])
def test_presentation_probability_policy_is_rng_injectable(
    difficulty, expected, tolerance, domain
):
    task = SimpleNamespace(
        id=101,
        difficulty=difficulty,
        multiple_choice_prompt=f"{domain} question",
        options={"A": "one", "B": "two", "C": "three", "D": "four"},
        correct_option="B",
    )
    rng = Random(20260911)
    choices = [choose_presentation_type(task, rng) for _ in range(10_000)]
    observed = choices.count("MULTIPLE_CHOICE") / len(choices)
    assert abs(observed - expected) <= tolerance


def test_presentation_choice_has_no_task_number_coupling():
    tasks = [
        SimpleNamespace(
            id=task_id,
            difficulty="BRONZE",
            multiple_choice_prompt="question",
            options={"A": "one", "B": "two", "C": "three", "D": "four"},
            correct_option="A",
        )
        for task_id in (1, 2)
    ]
    observed = [choose_presentation_type(task, Random(7)) for task in tasks]
    assert observed[0] == observed[1]
    assert tasks[0].id % 2 != tasks[1].id % 2


def test_attempt_option_shuffle_varies_answer_position_and_is_stable_per_rng():
    options = {"A": "correct", "B": "near miss", "C": "boundary error", "D": "wrong order"}
    positions = {
        shuffled_options(options, "A", Random(seed))[1]
        for seed in range(20)
    }
    assert positions == {"A", "B", "C", "D"}
    assert shuffled_options(options, "A", Random(11)) == shuffled_options(
        options, "A", Random(11)
    )


class _ExistingPresentationSession:
    def __init__(self, task, user, concept, presentation):
        self.values = [task, user, presentation]
        self.concept = concept
        self.commits = 0

    def scalar(self, _statement):
        return self.values.pop(0)

    def get(self, _model, _identifier):
        return self.concept

    def commit(self):
        self.commits += 1


class _RngMustNotRun:
    def random(self):
        raise AssertionError("persisted presentation must not reroll")

    def shuffle(self, _values):
        raise AssertionError("persisted options must not reshuffle")


def test_active_presentation_is_reused_without_rerolling_mode_or_options():
    task = SimpleNamespace(id=3, public_id=uuid.uuid4(), concept_id=4, is_active=True)
    user = SimpleNamespace(id=5)
    concept = SimpleNamespace(id=4)
    presentation = SimpleNamespace(
        presentation_type="MULTIPLE_CHOICE",
        options={"A": "wrong", "B": "correct", "C": "near", "D": "boundary"},
        correct_option="B",
    )
    db = _ExistingPresentationSession(task, user, concept, presentation)

    result = start_task_presentation(db, task.public_id, user, rng=_RngMustNotRun())

    assert result == (presentation, task, concept)
    assert db.commits == 0


def test_completion_identity_does_not_include_presentation_mode():
    from app.models.task_completion import TaskCompletion

    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in TaskCompletion.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("user_id", "task_id") in unique_columns


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
    assert all(task.difficulty in {"BRONZE", "SILVER"} for task in first_day)


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


def test_daily_recommendation_deduplicates_seeded_story_variants():
    tasks = [
        SimpleNamespace(
            id=1,
            concept_id=10,
            difficulty="BRONZE",
            type="CODE",
            title="[SAMPLE:PYTHON:BRONZE:001] 🐾 간식 시간: 두 수의 합",
            description="[도와주세요!] 첫 이야기\n\n[문제] 두 정수 a, b를 읽고 합을 출력하세요.",
        ),
        SimpleNamespace(
            id=2,
            concept_id=10,
            difficulty="BRONZE",
            type="CODE",
            title="[SAMPLE:PYTHON:BRONZE:011] 🐾 장난감 정리: 두 수의 합",
            description="[도와주세요!] 다른 이야기\n\n[문제] 두 정수 a, b를 읽고 합을 출력하세요.",
        ),
        SimpleNamespace(
            id=3,
            concept_id=10,
            difficulty="BRONZE",
            type="CODE",
            title="[SAMPLE:PYTHON:BRONZE:002] 🐾 간식 시간: 문자열 길이",
            description="[도와주세요!] 셋째 이야기\n\n[문제] 문자열 한 줄을 읽고 글자 수를 출력하세요.",
        ),
    ]

    selected = _diversify_daily_tasks(tasks, 7, date(2026, 9, 11), [], 3)

    assert len(selected) == 2
    assert len({_task_problem_key(task) for task in selected}) == 2


@pytest.mark.parametrize("rows", [build_tasks(), build_sql_tasks()])
def test_seeded_recommendation_page_contains_varied_concepts(rows):
    concept_ids = {name: index for index, name in enumerate(sorted({row["concept"] for row in rows}), 1)}
    tasks = [
        SimpleNamespace(
            id=index,
            concept_id=concept_ids[row["concept"]],
            difficulty=row["difficulty"],
            type=row["type"],
            title=row["title"],
            description=row["description"],
        )
        for index, row in enumerate(rows, 1)
    ]

    selected = _diversify_daily_tasks(tasks, 17, date(2026, 9, 10), [], 10)

    assert len({task.concept_id for task in selected}) >= 7
    assert len({_task_problem_key(task) for task in selected}) == len(selected)
    assert all(task.type == "CODE" for task in selected)


def test_seed_has_150_balanced_unique_tasks_and_hidden_answers():
    rows = build_tasks()
    assert len(rows) == len({row["title"] for row in rows}) == 150
    assert {level: sum(row["difficulty"] == level for row in rows) for level in ("BRONZE", "SILVER", "GOLD")} == {"BRONZE": 50, "SILVER": 50, "GOLD": 50}
    assert all(row["type"] == "CODE" and row["test_cases"] != "[]" for row in rows)
    choices = [row for row in rows if row["options"]]
    assert len(choices) == 100
    assert {row["correct_option"] for row in choices} == {"A", "B", "C", "D"}
    assert all(row["multiple_choice_prompt"] for row in choices)
    assert all(len(row["options"]) == len(set(row["options"].values())) == 4 for row in choices)
    assert all(row["options"] is None for row in rows if row["difficulty"] == "GOLD")
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
    assert all(row["type"] == "CODE" and row["test_cases"] != "[]" for row in rows)
    choices = [row for row in rows if row["options"]]
    assert len(choices) == 100
    assert {row["correct_option"] for row in choices} == {"A", "B", "C", "D"}
    assert all(len(row["options"]) == len(set(row["options"].values())) == 4 for row in choices)
    assert all(row["options"] is None for row in rows if row["difficulty"] == "GOLD")
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
    assert "tasks.type =" not in sql
    assert "concepts.domain =" in sql
    assert "tasks.difficulty =" in sql
    assert "tasks.concept_id =" in sql
    assert "ORDER BY tasks.id" in sql
    assert "LIMIT" in sql


def test_multiple_choice_filter_selects_capable_non_gold_tasks():
    concept = SimpleNamespace(id=9, public_id=uuid.uuid4(), domain="SQL", name="joins")
    db = _LearningTaskSession(concept, [], [])

    list_tasks(
        db=db,
        user=SimpleNamespace(id=7, learning_reset_at=None),
        task_type="MULTIPLE_CHOICE",
        limit=5,
    )

    sql = str(db.scalar_statements[0])
    assert "tasks.options IS NOT NULL" in sql
    assert "tasks.difficulty !=" in sql
    assert "tasks.type =" not in sql


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
