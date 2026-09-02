import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

EXPECTED_TABLES = [
    "users", "cats", "cat_memories", "concepts", "items",
    "tasks", "task_attempts", "attendances", "attendance_tasks",
    "rooms", "room_participants", "room_tasks", "user_cats",
    "user_proficiency", "placed_objects", "gacha_executions",
]


def test_all_16_tables_exist(engine):
    """16개 테이블이 실제 DB에 전부 존재하는지 확인"""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
        actual_tables = {row[0] for row in result}

    missing = set(EXPECTED_TABLES) - actual_tables
    assert not missing, f"누락된 테이블: {missing}"


def test_public_id_auto_generated(db_session):
    """새 row 생성 시 public_id(UUID)가 자동으로 채워지는지 확인"""
    db_session.execute(
        text(
            "INSERT INTO users (email, username, role, balance, mileage, house_level) "
            "VALUES ('test@example.com', 'testuser', 'STUDENT', 0, 0, 1)"
        )
    )
    row = db_session.execute(
        text("SELECT public_id FROM users WHERE email = 'test@example.com'")
    ).fetchone()

    assert row is not None
    assert row[0] is not None
    assert isinstance(uuid.UUID(str(row[0])), uuid.UUID)


def test_gacha_execution_status_check_constraint(db_session):
    """status에 계약서 외 값이 들어가면 DB가 거부하는지 확인"""
    db_session.execute(
        text(
            "INSERT INTO users (email, username, role, balance, mileage, house_level) "
            "VALUES ('gacha_test@example.com', 'gachauser', 'STUDENT', 100, 0, 1)"
        )
    )
    user_id = db_session.execute(
        text("SELECT id FROM users WHERE email = 'gacha_test@example.com'")
    ).scalar()

    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO gacha_executions "
                "(user_id, request_id, request_payload, request_hash, "
                "operation_type, status, balance_cost) "
                "VALUES (:user_id, gen_random_uuid(), '{}', 'hash', 'GACHA', "
                "'INVALID_STATUS', 10)"
            ),
            {"user_id": user_id},
        )


def test_gacha_execution_balance_cost_nonnegative(db_session):
    """balance_cost가 음수면 DB가 거부하는지 확인"""
    db_session.execute(
        text(
            "INSERT INTO users (email, username, role, balance, mileage, house_level) "
            "VALUES ('gacha_test2@example.com', 'gachauser2', 'STUDENT', 100, 0, 1)"
        )
    )
    user_id = db_session.execute(
        text("SELECT id FROM users WHERE email = 'gacha_test2@example.com'")
    ).scalar()

    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO gacha_executions "
                "(user_id, request_id, request_payload, request_hash, "
                "operation_type, status, balance_cost) "
                "VALUES (:user_id, gen_random_uuid(), '{}', 'hash', 'GACHA', "
                "'ACQUIRED', -10)"
            ),
            {"user_id": user_id},
        )