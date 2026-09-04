import pytest

from app.modules.grading.sql_sandbox import UnsafeSQL, validate_read_only_sql, validate_sql


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


def test_mode_specific_dml_and_ddl_are_allowed_but_dangerous_sql_is_not():
    validate_sql("UPDATE cats SET name = 'Nabi' WHERE id = 1", "MUTATION")
    validate_sql("CREATE TABLE toys (id int)", "SCHEMA")
    with pytest.raises(UnsafeSQL):
        validate_sql("GRANT ALL ON cats TO public", "SCHEMA")
    with pytest.raises(UnsafeSQL):
        validate_sql("ALTER ROLE grader_admin PASSWORD 'broken'", "SCHEMA")
    with pytest.raises(UnsafeSQL):
        validate_sql("CREATE FUNCTION danger() RETURNS void LANGUAGE SQL AS 'SELECT 1'", "SCHEMA")
    with pytest.raises(UnsafeSQL):
        validate_sql("SELECT set_config('statement_timeout', '0', false)", "QUERY")
    with pytest.raises(UnsafeSQL):
        validate_sql("UPDATE cats SET name = 'x'; DELETE FROM cats", "MUTATION")
