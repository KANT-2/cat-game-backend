from app.models.gacha_execution import GachaExecution


def test_balance_cost_defaults_to_zero() -> None:
    column = GachaExecution.__table__.c.balance_cost

    assert column.default is not None
    assert column.default.arg == 0
    assert column.server_default is not None
    assert str(column.server_default.arg) == "0"
