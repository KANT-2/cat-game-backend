import json
import re
import threading
import uuid
from collections.abc import Callable
from contextlib import closing

import psycopg
from psycopg import sql

from app.core.config import settings
from app.modules.grading.sandbox.runner import GradeResult, Verdict
from app.modules.grading.test_cases import TestCase


class UnsafeSQL(ValueError):
    pass


_BLOCKED = {
    "ALTER", "ANALYZE", "CALL", "COMMENT", "COPY", "CREATE", "DELETE", "DO",
    "DROP", "EXECUTE", "GRANT", "INSERT", "LOCK", "MERGE", "REFRESH", "REINDEX",
    "REVOKE", "SECURITY", "SET", "TRUNCATE", "UPDATE", "VACUUM",
}
_READ_PREFIXES = {"SELECT", "TABLE", "VALUES", "WITH"}


def _tokens_and_semicolons(statement: str) -> tuple[list[str], list[int]]:
    """Lex SQL while ignoring quoted text/comments; enough for a strict read-only gate."""
    scrubbed: list[str] = []
    semicolons: list[int] = []
    i = 0
    state = "normal"
    dollar_tag = ""
    while i < len(statement):
        pair = statement[i:i + 2]
        char = statement[i]
        if state == "normal":
            if pair == "--":
                state = "line_comment"; scrubbed.extend("  "); i += 2; continue
            if pair == "/*":
                state = "block_comment"; scrubbed.extend("  "); i += 2; continue
            if char in ("'", '"'):
                state = "single" if char == "'" else "double"; scrubbed.append(" "); i += 1; continue
            if char == "$":
                match = re.match(r"\$[A-Za-z_][A-Za-z_0-9]*\$|\$\$", statement[i:])
                if match:
                    dollar_tag = match.group(0); state = "dollar"
                    scrubbed.extend(" " * len(dollar_tag)); i += len(dollar_tag); continue
            if char == ";":
                semicolons.append(i)
            scrubbed.append(char); i += 1; continue
        if state == "line_comment":
            scrubbed.append("\n" if char == "\n" else " ")
            if char == "\n": state = "normal"
            i += 1; continue
        if state == "block_comment":
            if pair == "*/": state = "normal"; scrubbed.extend("  "); i += 2
            else: scrubbed.append(" "); i += 1
            continue
        if state in ("single", "double"):
            quote = "'" if state == "single" else '"'
            if char == quote and statement[i:i + 2] == quote * 2:
                scrubbed.extend("  "); i += 2; continue
            scrubbed.append(" ")
            if char == quote: state = "normal"
            i += 1; continue
        if state == "dollar":
            if statement.startswith(dollar_tag, i):
                scrubbed.extend(" " * len(dollar_tag)); i += len(dollar_tag); state = "normal"
            else: scrubbed.append(" "); i += 1
    if state not in ("normal", "line_comment"):
        raise UnsafeSQL("unterminated SQL quote or comment")
    return re.findall(r"[A-Za-z_][A-Za-z_0-9]*", "".join(scrubbed).upper()), semicolons


def validate_read_only_sql(statement: str) -> None:
    tokens, semicolons = _tokens_and_semicolons(statement)
    if not tokens or tokens[0] not in _READ_PREFIXES:
        raise UnsafeSQL("only SELECT queries are allowed")
    if any(token in _BLOCKED for token in tokens):
        raise UnsafeSQL("statement contains a forbidden SQL operation")
    if len(semicolons) > 1 or (semicolons and statement[semicolons[0] + 1:].strip()):
        raise UnsafeSQL("multiple SQL statements are not allowed")


def _expected_rows(raw: str) -> list[list[object]]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("expected_output must be a JSON array of rows") from exc
    if not isinstance(value, list) or any(not isinstance(row, list) for row in value):
        raise ValueError("expected_output must be a JSON array of rows")
    return value


def _json_rows(rows: list[tuple]) -> bytes:
    return json.dumps(rows, default=str, separators=(",", ":"), ensure_ascii=False).encode()


class SQLSandbox:
    def __init__(self, connect: Callable = psycopg.connect) -> None:
        self._connect = connect
        self._slots = threading.BoundedSemaphore(settings.grading_max_concurrency)

    def grade(self, statement: str, cases: list[TestCase]) -> GradeResult:
        try:
            validate_read_only_sql(statement)
        except UnsafeSQL as exc:
            return GradeResult(Verdict.RUNTIME_ERROR, total=len(cases), detail=str(exc))
        secret = settings.sql_grading_database_url
        if secret is None:
            return GradeResult(Verdict.SYSTEM_ERROR, total=len(cases), detail="SQL grader is not configured")
        passed = 0
        with self._slots:
            for case in cases:
                result = self._grade_case(secret.get_secret_value(), statement, case)
                if result is not None:
                    return GradeResult(result.verdict, passed, len(cases), result.detail)
                passed += 1
        return GradeResult(Verdict.ACCEPTED, passed, len(cases))

    def _grade_case(self, dsn: str, statement: str, case: TestCase) -> GradeResult | None:
        schema = f"grade_{uuid.uuid4().hex}"
        try:
            expected = _expected_rows(case.expected_output)
            with closing(self._connect(
                dsn,
                autocommit=True,
                connect_timeout=settings.sql_grading_connect_timeout_seconds,
            )) as admin:
                admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
                try:
                    admin.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
                    admin.execute(case.input)
                    try:
                        with closing(self._connect(
                            dsn,
                            connect_timeout=settings.sql_grading_connect_timeout_seconds,
                        )) as submission, submission.transaction():
                            submission.execute("SET TRANSACTION READ ONLY")
                            submission.execute(
                                sql.SQL("SET LOCAL search_path TO {}, pg_catalog").format(
                                    sql.Identifier(schema)
                                )
                            )
                            submission.execute(
                                sql.SQL("SET LOCAL statement_timeout TO {}").format(
                                    sql.Literal(
                                        f"{settings.sql_grading_statement_timeout_ms}ms"
                                    )
                                )
                            )
                            cursor = submission.execute(statement)
                            rows = cursor.fetchmany(settings.sql_grading_max_rows + 1)
                            if len(rows) > settings.sql_grading_max_rows:
                                return GradeResult(
                                    Verdict.OUTPUT_LIMIT, detail="row limit exceeded"
                                )
                            if len(_json_rows(rows)) > settings.sql_grading_output_bytes:
                                return GradeResult(
                                    Verdict.OUTPUT_LIMIT, detail="output limit exceeded"
                                )
                            normalized = json.loads(_json_rows(rows))
                            if normalized != expected:
                                return GradeResult(Verdict.WRONG_ANSWER)
                    except psycopg.errors.QueryCanceled:
                        return GradeResult(Verdict.TIMEOUT, detail="statement timeout exceeded")
                    except psycopg.errors.SyntaxError:
                        return GradeResult(Verdict.SYNTAX_ERROR, detail="invalid SQL syntax")
                    except psycopg.Error:
                        return GradeResult(Verdict.RUNTIME_ERROR, detail="query execution failed")
                finally:
                    admin.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        except ValueError as exc:
            return GradeResult(Verdict.SYSTEM_ERROR, detail=str(exc))
        except psycopg.Error:
            return GradeResult(Verdict.SYSTEM_ERROR, detail="SQL grader execution failed")
        except Exception:  # noqa: BLE001 - never expose driver/DSN details at this boundary
            return GradeResult(Verdict.SYSTEM_ERROR, detail="SQL grader execution failed")
        return None


sql_sandbox = SQLSandbox()
