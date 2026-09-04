import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

EXPECTED_TABLES = [
    "users",
    "cats",
    "cat_memories",
    "concepts",
    "items",
    "tasks",
    "task_attempts",
    "attendances",
    "attendance_tasks",
    "rooms",
    "room_participants",
    "room_tasks",
    "assets",
    "user_proficiency",
    "placed_objects",
    "gacha_executions",
]


def test_pgcrypto_extension_enabled(engine):
    """최초 마이그레이션이 UUID 생성에 사용하는 확장을 활성화하는지 확인"""
    with engine.connect() as conn:
        installed = conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto')")
        ).scalar_one()

    assert installed is True


def test_all_16_tables_exist(engine):
    """16개 테이블이 실제 DB에 전부 존재하는지 확인"""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        actual_tables = {row[0] for row in result}

    missing = set(EXPECTED_TABLES) - actual_tables
    assert not missing, f"누락된 테이블: {missing}"


def test_asset_naming_migration_is_applied(engine):
    """보유 자산 테이블과 고양이 기억 FK가 새 이름을 사용하는지 확인"""
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                )
            )
        }
        memory_columns = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'cat_memories'"
                )
            )
        }

    assert "assets" in tables
    assert "user_cats" not in tables
    assert "cat_asset_id" in memory_columns
    assert "user_cat_id" not in memory_columns
    assert "asset_id" not in memory_columns


def test_placed_object_position_uses_xyz_coordinates(db_session):
    """배치 위치 JSON이 x, y, z 계약으로 저장되는지 확인"""
    user_id = db_session.execute(
        text(
            "INSERT INTO users "
            "(email, username, role, balance, mileage, house_level) "
            "VALUES ('xyz@example.com', 'xyz-user', 'STUDENT', 0, 0, 1) "
            "RETURNING id"
        )
    ).scalar_one()
    item_id = db_session.execute(
        text(
            "INSERT INTO items (category, name, price) "
            "VALUES ('FURNITURE', 'XYZ Chair', 0) RETURNING id"
        )
    ).scalar_one()
    db_session.execute(
        text("INSERT INTO assets (user_id, item_id, quantity) VALUES (:user_id, :item_id, 1)"),
        {"user_id": user_id, "item_id": item_id},
    )

    position_data = db_session.execute(
        text(
            "INSERT INTO placed_objects (user_id, item_id, position_data) "
            "VALUES (:user_id, :item_id, "
            '\'{"x": 10, "y": 20, "z": 30}\'::jsonb) '
            "RETURNING position_data"
        ),
        {"user_id": user_id, "item_id": item_id},
    ).scalar_one()

    assert position_data == {"x": 10, "y": 20, "z": 30}
    assert "rotation" not in position_data


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


def test_gacha_execution_balance_cost_defaults_to_zero(db_session):
    """claim 단계에서 비용을 생략하면 DB가 0을 사용한다."""
    db_session.execute(
        text(
            "INSERT INTO users (email, username, role, balance, mileage, house_level) "
            "VALUES ('gacha_default@example.com', 'gachadefault', 'STUDENT', 100, 0, 1)"
        )
    )
    user_id = db_session.execute(
        text("SELECT id FROM users WHERE email = 'gacha_default@example.com'")
    ).scalar_one()

    balance_cost = db_session.execute(
        text(
            "INSERT INTO gacha_executions "
            "(user_id, request_id, request_payload, request_hash, operation_type, status) "
            "VALUES (:user_id, gen_random_uuid(), '{}', 'hash-default', 'GACHA', 'ACQUIRED') "
            "RETURNING balance_cost"
        ),
        {"user_id": user_id},
    ).scalar_one()

    assert balance_cost == 0
