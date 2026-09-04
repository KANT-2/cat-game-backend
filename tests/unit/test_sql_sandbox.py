import pytest

from app.modules.grading.sql_sandbox import UnsafeSQL, validate_read_only_sql


@pytest.mark.parametrize("statement", [
    "INSERT INTO cats VALUES (1)",
    "UPDATE cats SET name = 'x'",
    "DELETE FROM cats",
    "DROP TABLE cats",
    "ALTER TABLE cats ADD COLUMN age int",
    "TRUNCATE cats",
    "CREATE TABLE cats (id int)",
    "GRANT SELECT ON cats TO public",
    "REVOKE SELECT ON cats FROM public",
    "COPY cats TO STDOUT",
    "CALL dangerous()",
    "DO $$ BEGIN NULL; END $$",
    "WITH gone AS (DELETE FROM cats RETURNING *) SELECT * FROM gone",
])
def test_rejects_mutating_and_dangerous_statements(statement):
    with pytest.raises(UnsafeSQL):
        validate_read_only_sql(statement)


def test_rejects_multiple_statements_but_allows_semicolons_in_literals():
    with pytest.raises(UnsafeSQL, match="multiple"):
        validate_read_only_sql("SELECT 1; SELECT 2")
    validate_read_only_sql("SELECT ';' AS value")


def test_allows_select_and_read_only_cte():
    validate_read_only_sql("SELECT id FROM cats ORDER BY id")
    validate_read_only_sql("WITH cats AS (SELECT 1 AS id) SELECT * FROM cats")
