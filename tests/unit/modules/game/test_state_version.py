from app.models.user import User


def test_game_state_version_advances_from_persisted_value() -> None:
    user = User(state_version=7)

    user.advance_state_version()

    assert user.state_version == 8


def test_game_state_version_advances_new_unflushed_user() -> None:
    user = User()

    user.advance_state_version()

    assert user.state_version == 2
