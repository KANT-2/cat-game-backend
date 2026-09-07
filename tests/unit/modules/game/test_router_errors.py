from app.core.exceptions import ItemAlreadyOwnedError
from app.modules.game.router import _http_error


def test_owned_background_purchase_uses_stable_game_reason() -> None:
    error = _http_error(ItemAlreadyOwnedError("item already owned"))

    assert error.status_code == 409
    assert error.detail == "already-owned"
