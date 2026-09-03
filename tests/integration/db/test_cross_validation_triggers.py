from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def _insert_user(db_session, email: str) -> int:
    return db_session.execute(
        text(
            "INSERT INTO users (email, username, role, balance, mileage, house_level) "
            "VALUES (:email, :email, 'STUDENT', 1000, 0, 1) RETURNING id"
        ),
        {"email": email},
    ).scalar_one()


def _insert_item(db_session, category: str, name: str) -> int:
    return db_session.execute(
        text(
            "INSERT INTO items (category, name, price) "
            "VALUES (:category, :name, 100) RETURNING id"
        ),
        {"category": category, "name": name},
    ).scalar_one()


def _insert_item_asset(db_session, user_id: int, item_id: int, quantity: int = 1) -> int:
    return db_session.execute(
        text(
            "INSERT INTO user_cats (user_id, item_id, quantity) "
            "VALUES (:user_id, :item_id, :quantity) RETURNING id"
        ),
        {"user_id": user_id, "item_id": item_id, "quantity": quantity},
    ).scalar_one()


def _insert_cat_asset(db_session, user_id: int) -> int:
    cat_id = db_session.execute(
        text(
            "INSERT INTO cats (name, persona, rarity) "
            "VALUES ('trigger cat', 'calm', 'COMMON') RETURNING id"
        )
    ).scalar_one()
    return db_session.execute(
        text(
            "INSERT INTO user_cats (user_id, cat_id, quantity) "
            "VALUES (:user_id, :cat_id, 1) RETURNING id"
        ),
        {"user_id": user_id, "cat_id": cat_id},
    ).scalar_one()


def test_surface_asset_trigger_accepts_owned_surface_and_rejects_unowned(db_session):
    owner_id = _insert_user(db_session, "surface-owner@example.com")
    other_id = _insert_user(db_session, "surface-other@example.com")
    wallpaper_id = _insert_item(db_session, "WALLPAPER", "trigger wallpaper")
    _insert_item_asset(db_session, owner_id, wallpaper_id)

    db_session.execute(
        text("UPDATE users SET wallpaper_item_id = :item_id WHERE id = :user_id"),
        {"item_id": wallpaper_id, "user_id": owner_id},
    )

    with pytest.raises(DBAPIError, match="does not own item"):
        db_session.execute(
            text("UPDATE users SET wallpaper_item_id = :item_id WHERE id = :user_id"),
            {"item_id": wallpaper_id, "user_id": other_id},
        )


def test_task_attempt_context_trigger_accepts_owner_and_rejects_other_user(db_session):
    owner_id = _insert_user(db_session, "daily-owner@example.com")
    other_id = _insert_user(db_session, "daily-other@example.com")
    concept_id = db_session.execute(
        text("INSERT INTO concepts (name) VALUES ('trigger concept') RETURNING id")
    ).scalar_one()
    task_id = db_session.execute(
        text(
            "INSERT INTO tasks "
            "(concept_id, title, type, difficulty, description, template_code, "
            "test_cases, is_active) VALUES "
            "(:concept_id, 'trigger task', 'CODE', 'BRONZE', 'desc', 'code', '[]', true) "
            "RETURNING id"
        ),
        {"concept_id": concept_id},
    ).scalar_one()
    attendance_id = db_session.execute(
        text(
            "INSERT INTO attendances (user_id, check_in_date, streak_count) "
            "VALUES (:user_id, :check_in_date, 1) RETURNING id"
        ),
        {"user_id": owner_id, "check_in_date": date(2026, 9, 2)},
    ).scalar_one()
    attendance_task_id = db_session.execute(
        text(
            "INSERT INTO attendance_tasks "
            "(attendance_id, task_id, task_order, is_completed) "
            "VALUES (:attendance_id, :task_id, 1, false) RETURNING id"
        ),
        {"attendance_id": attendance_id, "task_id": task_id},
    ).scalar_one()

    statement = text(
        "INSERT INTO task_attempts "
        "(user_id, task_id, attendance_task_id, context_type, submitted_code, status, used_hint) "
        "VALUES (:user_id, :task_id, :attendance_task_id, 'DAILY', 'code', 'PENDING', false)"
    )
    params = {"task_id": task_id, "attendance_task_id": attendance_task_id}
    db_session.execute(statement, {**params, "user_id": owner_id})

    with pytest.raises(DBAPIError, match="cannot submit"):
        db_session.execute(statement, {**params, "user_id": other_id})


def test_placed_object_trigger_accepts_owned_quantity_and_rejects_excess(db_session):
    user_id = _insert_user(db_session, "placement@example.com")
    item_id = _insert_item(db_session, "FURNITURE", "trigger chair")
    _insert_item_asset(db_session, user_id, item_id)
    statement = text(
        "INSERT INTO placed_objects (user_id, item_id, position_data) "
        "VALUES (:user_id, :item_id, '{}'::jsonb)"
    )

    db_session.execute(statement, {"user_id": user_id, "item_id": item_id})

    with pytest.raises(DBAPIError, match="cannot place another instance"):
        db_session.execute(statement, {"user_id": user_id, "item_id": item_id})


def test_reverse_reference_trigger_rejects_deleting_placed_asset(db_session):
    user_id = _insert_user(db_session, "reverse-reference@example.com")
    item_id = _insert_item(db_session, "FURNITURE", "trigger table")
    asset_id = _insert_item_asset(db_session, user_id, item_id)
    db_session.execute(
        text(
            "INSERT INTO placed_objects (user_id, item_id, position_data) "
            "VALUES (:user_id, :item_id, '{}'::jsonb)"
        ),
        {"user_id": user_id, "item_id": item_id},
    )

    with pytest.raises(DBAPIError, match="cannot reduce item"):
        db_session.execute(text("DELETE FROM user_cats WHERE id = :id"), {"id": asset_id})


def test_cat_memory_trigger_accepts_cat_asset_and_rejects_item_asset(db_session):
    user_id = _insert_user(db_session, "memory@example.com")
    cat_asset_id = _insert_cat_asset(db_session, user_id)
    item_id = _insert_item(db_session, "FURNITURE", "memory-invalid-item")
    item_asset_id = _insert_item_asset(db_session, user_id, item_id)
    statement = text(
        "INSERT INTO cat_memories (user_cat_id, context_summary) "
        "VALUES (:user_cat_id, 'summary')"
    )

    db_session.execute(statement, {"user_cat_id": cat_asset_id})

    with pytest.raises(DBAPIError, match="does not reference a cat asset"):
        db_session.execute(statement, {"user_cat_id": item_asset_id})
