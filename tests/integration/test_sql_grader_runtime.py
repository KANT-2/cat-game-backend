import os

import psycopg
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.modules.grading.sandbox.runner import Verdict
from app.modules.grading.sql_sandbox import SQLSandbox
from app.modules.grading.test_cases import TestCase as Case

DSN = os.getenv(
    "SQL_GRADING_TEST_DATABASE_URL",
    os.getenv(
        "SQL_GRADING_DATABASE_URL",
        "postgresql://grader_admin:local-grader-only@127.0.0.1:55432/sql_grader",
    ),
)


def _postgres_available() -> bool:
    try:
        with psycopg.connect(DSN, connect_timeout=1):
            return True
    except psycopg.Error:
        return False


pytestmark = pytest.mark.skipif(not _postgres_available(), reason="SQL grader PostgreSQL is not running")


@pytest.fixture(autouse=True)
def sql_settings(monkeypatch):
    monkeypatch.setattr(settings, "sql_grading_database_url", SecretStr(DSN))
    monkeypatch.setattr(settings, "sql_grading_connect_timeout_seconds", 3)
    monkeypatch.setattr(settings, "sql_grading_statement_timeout_ms", 100)
    monkeypatch.setattr(settings, "sql_grading_max_rows", 2)
    monkeypatch.setattr(settings, "sql_grading_output_bytes", 32)


def case(expected='[[1,"Miso"],[2,"Nabi"]]'):
    return Case(
        "CREATE TABLE cats (id int, name text); "
        "INSERT INTO cats VALUES (1, 'Miso'), (2, 'Nabi')",
        expected,
    )


def test_select_accepted_and_mismatch_wrong_answer():
    runner = SQLSandbox()
    statement = "SELECT id, name FROM cats ORDER BY id"
    assert runner.grade(statement, [case()]).verdict is Verdict.ACCEPTED
    assert runner.grade(statement, [case('[[9,"Other"]]')]).verdict is Verdict.WRONG_ANSWER


def test_forbidden_and_multiple_statements_are_blocked():
    runner = SQLSandbox()
    assert runner.grade("DELETE FROM cats", [case()]).verdict is Verdict.RUNTIME_ERROR
    assert runner.grade("SELECT 1; SELECT 2", [case()]).verdict is Verdict.RUNTIME_ERROR


def test_timeout_and_limits():
    runner = SQLSandbox()
    assert runner.grade("SELECT pg_sleep(1)", [Case("SELECT 1", "[[null]]")]).verdict is Verdict.TIMEOUT
    assert runner.grade("SELECT * FROM generate_series(1, 3)", [Case("SELECT 1", "[]")]).verdict is Verdict.OUTPUT_LIMIT
    monkey = "x" * 40
    assert runner.grade("SELECT '" + monkey + "'", [Case("SELECT 1", "[]")]).verdict is Verdict.OUTPUT_LIMIT


def test_each_submission_gets_clean_seed_state():
    runner = SQLSandbox()
    first = runner.grade("SELECT count(*) FROM cats", [case("[[2]]")])
    second = runner.grade("SELECT count(*) FROM cats", [case("[[2]]")])
    assert first.verdict is second.verdict is Verdict.ACCEPTED


def test_mutation_and_schema_modes_are_graded_then_rolled_back():
    runner = SQLSandbox()
    mutation = Case(
        case().input,
        '{"mode":"MUTATION","verification_query":"SELECT name FROM cats WHERE id=1",'
        '"expected_rows":[["Bori"]]}',
    )
    assert runner.grade("UPDATE cats SET name='Bori' WHERE id=1", [mutation]).verdict is Verdict.ACCEPTED
    assert runner.grade("UPDATE cats SET name='Wrong' WHERE id=1", [mutation]).verdict is Verdict.WRONG_ANSWER

    schema = Case(
        "SELECT 1",
        '{"mode":"SCHEMA","verification_query":"SELECT column_name FROM '
        "information_schema.columns WHERE table_schema=current_schema() AND table_name='toys' "
        'ORDER BY ordinal_position","expected_rows":[["id"],["name"]]}',
    )
    assert runner.grade("CREATE TABLE toys (id int, name text)", [schema]).verdict is Verdict.ACCEPTED
    assert runner.grade("CREATE TABLE toys (id int)", [schema]).verdict is Verdict.WRONG_ANSWER

    # A following query starts from the original seed, never from a prior submission.
    assert runner.grade("SELECT name FROM cats WHERE id=1", [case('[["Miso"]]')]).verdict is Verdict.ACCEPTED
