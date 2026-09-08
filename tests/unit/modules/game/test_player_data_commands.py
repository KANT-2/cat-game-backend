from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.user import User
from app.modules.game.commands import clear_cat_memories, reset_learning_progress


def test_reset_learning_progress_removes_progress_without_changing_balance() -> None:
    user = User(id=7, balance=940, state_version=12)
    db = MagicMock()
    db.scalar.return_value = user
    db.execute.side_effect = [
        SimpleNamespace(rowcount=3),
        SimpleNamespace(rowcount=1),
    ]

    result = reset_learning_progress(db, user)

    assert result["removed_proficiencies"] == 3
    assert isinstance(result["reset_at"], str)
    assert user.balance == 940
    assert user.state_version == 13
    assert user.learning_reset_at is not None
    statements = [str(call.args[0]) for call in db.execute.call_args_list]
    assert statements[0].startswith("DELETE FROM user_proficiency")
    assert statements[1].startswith("UPDATE attendance_tasks")
    db.commit.assert_called_once()


def test_clear_cat_memories_is_scoped_to_owned_cat_assets() -> None:
    user = User(id=11, state_version=12)
    db = MagicMock()
    db.scalar.return_value = user
    db.execute.return_value = SimpleNamespace(rowcount=4)

    result = clear_cat_memories(db, user)

    assert result == {"removed": 4}
    assert user.state_version == 13
    statement = str(db.execute.call_args.args[0])
    assert statement.startswith("DELETE FROM cat_memories")
    assert "assets.user_id" in statement
    assert "assets.cat_id IS NOT NULL" in statement
    db.commit.assert_called_once()
