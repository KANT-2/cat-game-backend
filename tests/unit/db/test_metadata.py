from app.db.base import Base as DbBase
from app.models import Base as ModelBase

EXPECTED_TABLES = {
    "attendance_tasks",
    "attendances",
    "cat_memories",
    "cats",
    "concepts",
    "gacha_executions",
    "items",
    "placed_objects",
    "room_participants",
    "room_tasks",
    "rooms",
    "task_attempts",
    "tasks",
    "user_cats",
    "user_proficiency",
    "users",
}


def test_application_uses_one_declarative_base() -> None:
    assert DbBase is ModelBase


def test_all_models_are_registered_in_alembic_metadata() -> None:
    assert set(ModelBase.metadata.tables) == EXPECTED_TABLES
