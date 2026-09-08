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


_ALWAYS_BLOCKED = {
    "ANALYZE",
    "CALL",
    "COMMENT",
    "COPY",
    "DO",
    "EXECUTE",
    "GRANT",
    "LOCK",
    "LO_EXPORT",
    "LO_IMPORT",
    "MERGE",
    "PG_CANCEL_BACKEND",
    "PG_READ_FILE",
    "PG_TERMINATE_BACKEND",
    "PG_WRITE_FILE",
    "REFRESH",
    "REINDEX",
    "REVOKE",
    "SECURITY",
    "SET_CONFIG",
    "TRUNCATE",
    "VACUUM",
}
_READ_PREFIXES = {"SELECT", "TABLE", "VALUES", "WITH"}
_MODE_PREFIXES = {
    "QUERY": _READ_PREFIXES,
    "MUTATION": {"INSERT", "UPDATE", "DELETE"},
    "SCHEMA": {"CREATE", "ALTER", "DROP"},
}
_SCHEMA_OBJECTS = {
    "CREATE": {"TABLE", "INDEX", "VIEW"},
    "ALTER": {"TABLE"},
    "DROP": {"TABLE", "INDEX", "VIEW"},
}


def _tokens_and_semicolons(statement: str) -> tuple[list[str], list[int]]:
    """Lex SQL while ignoring quoted text/comments; enough for a strict read-only gate."""
    scrubbed: list[str] = []
    semicolons: list[int] = []
    i = 0
    state = "normal"
    dollar_tag = ""
    while i < len(statement):
        pair = statement[i : i + 2]
        char = statement[i]
        if state == "normal":
            if pair == "--":
                state = "line_comment"
                scrubbed.extend("  ")
                i += 2
                continue
            if pair == "/*":
                state = "block_comment"
                scrubbed.extend("  ")
                i += 2
                continue
            if char in ("'", '"'):
                state = "single" if char == "'" else "double"
                scrubbed.append(" ")
                i += 1
                continue
            if char == "$":
                match = re.match(r"\$[A-Za-z_][A-Za-z_0-9]*\$|\$\$", statement[i:])
                if match:
                    dollar_tag = match.group(0)
                    state = "dollar"
                    scrubbed.extend(" " * len(dollar_tag))
                    i += len(dollar_tag)
                    continue
            if char == ";":
                semicolons.append(i)
            scrubbed.append(char)
            i += 1
            continue
        if state == "line_comment":
            scrubbed.append("\n" if char == "\n" else " ")
            if char == "\n":
                state = "normal"
            i += 1
            continue
        if state == "block_comment":
            if pair == "*/":
                state = "normal"
                scrubbed.extend("  ")
                i += 2
            else:
                scrubbed.append(" ")
                i += 1
            continue
        if state in ("single", "double"):
            quote = "'" if state == "single" else '"'
            if char == quote and statement[i : i + 2] == quote * 2:
                scrubbed.extend("  ")
                i += 2
                continue
            scrubbed.append(" ")
            if char == quote:
                state = "normal"
            i += 1
            continue
        if state == "dollar":
            if statement.startswith(dollar_tag, i):
                scrubbed.extend(" " * len(dollar_tag))
                i += len(dollar_tag)
                state = "normal"
            else:
                scrubbed.append(" ")
                i += 1
    if state not in ("normal", "line_comment"):
        raise UnsafeSQL("unterminated SQL quote or comment")
    return re.findall(r"[A-Za-z_][A-Za-z_0-9]*", "".join(scrubbed).upper()), semicolons


def validate_sql(statement: str, mode: str = "QUERY") -> None:
    tokens, semicolons = _tokens_and_semicolons(statement)
    allowed = _MODE_PREFIXES.get(mode)
    if allowed is None or not tokens or tokens[0] not in allowed:
        raise UnsafeSQL(f"statement is not allowed in {mode} mode")
    if any(token in _ALWAYS_BLOCKED for token in tokens):
        raise UnsafeSQL("statement contains a forbidden SQL operation")
    if mode == "QUERY" and any(
        token in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"} for token in tokens
    ):
        raise UnsafeSQL("statement contains a forbidden SQL operation")
    if mode == "SCHEMA" and (len(tokens) < 2 or tokens[1] not in _SCHEMA_OBJECTS[tokens[0]]):
        raise UnsafeSQL("only table, index, and view schema operations are allowed")
    if len(semicolons) > 1 or (semicolons and statement[semicolons[0] + 1 :].strip()):
        raise UnsafeSQL("multiple SQL statements are not allowed")


def validate_read_only_sql(statement: str) -> None:
    validate_sql(statement, "QUERY")


def _expected_spec(raw: str) -> tuple[str, str | None, str | None, list[list[object]] | None]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("expected_output must be valid JSON") from exc
    if isinstance(value, list) and not any(not isinstance(row, list) for row in value):
        return "QUERY", None, None, value
    if not isinstance(value, dict):
        raise TypeError("expected_output must be rows or a SQL grading specification")
    mode = value.get("mode")
    query = value.get("verification_query")
    reference_query = value.get("reference_query")
    rows = value.get("expected_rows")
    if mode == "QUERY" and isinstance(reference_query, str):
        validate_read_only_sql(reference_query)
        return mode, None, reference_query, None
    if mode not in {"MUTATION", "SCHEMA"} or not isinstance(query, str):
        raise ValueError("invalid SQL grading mode or verification query")
    if not isinstance(rows, list) or any(not isinstance(row, list) for row in rows):
        raise ValueError("expected_rows must be a JSON array of rows")
    validate_read_only_sql(query)
    return mode, query, None, rows


def _json_rows(rows: list[tuple]) -> bytes:
    return json.dumps(rows, default=str, separators=(",", ":"), ensure_ascii=False).encode()


class SQLSandbox:
    def __init__(self, connect: Callable = psycopg.connect) -> None:
        self._connect = connect
        self._slots = threading.BoundedSemaphore(settings.grading_max_concurrency)

    def grade(self, statement: str, cases: list[TestCase]) -> GradeResult:
        secret = settings.sql_grading_database_url
        if secret is None:
            return GradeResult(
                Verdict.SYSTEM_ERROR, total=len(cases), detail="SQL grader is not configured"
            )
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
            mode, verification_query, reference_query, expected = _expected_spec(
                case.expected_output
            )
            try:
                validate_sql(statement, mode)
            except UnsafeSQL as exc:
                return GradeResult(Verdict.RUNTIME_ERROR, detail=str(exc))
            with closing(
                self._connect(
                    dsn,
                    autocommit=True,
                    connect_timeout=settings.sql_grading_connect_timeout_seconds,
                )
            ) as admin:
                admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
                try:
                    admin.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
                    admin.execute(case.input)
                    try:
                        with closing(
                            self._connect(
                                dsn,
                                connect_timeout=settings.sql_grading_connect_timeout_seconds,
                            )
                        ) as submission:
                            if mode == "QUERY":
                                submission.execute("SET TRANSACTION READ ONLY")
                            submission.execute(
                                sql.SQL("SET LOCAL search_path TO {}, pg_catalog").format(
                                    sql.Identifier(schema)
                                )
                            )
                            submission.execute(
                                sql.SQL("SET LOCAL statement_timeout TO {}").format(
                                    sql.Literal(f"{settings.sql_grading_statement_timeout_ms}ms")
                                )
                            )
                            cursor = submission.execute(statement)
                            if verification_query is not None:
                                cursor = submission.execute(verification_query)
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
                            if reference_query is not None:
                                expected_cursor = submission.execute(reference_query)
                                expected_rows = expected_cursor.fetchmany(
                                    settings.sql_grading_max_rows + 1
                                )
                                if len(expected_rows) > settings.sql_grading_max_rows:
                                    raise ValueError("reference query exceeds the row limit")
                                if (
                                    len(_json_rows(expected_rows))
                                    > settings.sql_grading_output_bytes
                                ):
                                    raise ValueError("reference query exceeds the output limit")
                                expected = json.loads(_json_rows(expected_rows))
                            if normalized != expected:
                                return GradeResult(Verdict.WRONG_ANSWER)
                            submission.rollback()
                    except psycopg.errors.QueryCanceled:
                        return GradeResult(Verdict.TIMEOUT, detail="statement timeout exceeded")
                    except psycopg.errors.SyntaxError:
                        return GradeResult(Verdict.SYNTAX_ERROR, detail="invalid SQL syntax")
                    except psycopg.Error:
                        return GradeResult(Verdict.RUNTIME_ERROR, detail="query execution failed")
                finally:
                    admin.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
                    )
        except (TypeError, ValueError) as exc:
            return GradeResult(Verdict.SYSTEM_ERROR, detail=str(exc))
        except psycopg.Error:
            return GradeResult(Verdict.SYSTEM_ERROR, detail="SQL grader execution failed")
        except Exception:  # noqa: BLE001 - never expose driver/DSN details at this boundary
            return GradeResult(Verdict.SYSTEM_ERROR, detail="SQL grader execution failed")
        return None


sql_sandbox = SQLSandbox()
