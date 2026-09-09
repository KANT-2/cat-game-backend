import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import InsufficientBalanceError
from app.models.asset import Asset
from app.models.cat import Cat
from app.models.item import Item
from app.models.user import User
from app.modules.game.gacha import draw_game_gacha
from tests.fakes.repositories import (
    FakeAssetRepository,
    FakeCatRepository,
    FakeExecutionRepository,
    FakeItemRepository,
    FakeUserRepository,
)


def _user(balance: int = 100) -> User:
    return User(
        id=1,
        public_id=uuid.uuid4(),
        email="game-gacha@example.com",
        username="player",
        role="STUDENT",
        balance=balance,
        mileage=0,
        house_level=1,
    )


def _unit_of_work(user: User):
    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository(
        [
            Cat(
                id=2,
                public_id=uuid.uuid4(),
                catalog_key="ink",
                name="먹구름",
                persona="curious",
                rarity="RARE",
            )
        ]
    )
    unit_of_work.items = FakeItemRepository(
        [
            Item(
                id=3,
                public_id=uuid.uuid4(),
                catalog_key="furniture.desk",
                category="FURNITURE",
                name="공부 책상",
                price=3_900,
            )
        ]
    )
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()
    return unit_of_work


def test_game_gacha_charges_and_grants_furniture_once() -> None:
    user = _user()
    unit_of_work = _unit_of_work(user)
    source = MagicMock()
    source.random.return_value = 0.06
    request_id = uuid.uuid4()

    first = draw_game_gacha(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=request_id,
        draw_count=1,
        random_source=source,
    )
    replay = draw_game_gacha(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=request_id,
        draw_count=1,
        random_source=source,
    )

    assert first == replay
    assert first["remaining_balance"] == 70
    assert first["rewards"][0]["shop_item_id"] == "furniture.desk"
    assert unit_of_work.assets.assets[0].quantity == 1
    assert user.balance == 70


def test_game_gacha_does_not_charge_when_balance_is_insufficient() -> None:
    user = _user(balance=29)
    unit_of_work = _unit_of_work(user)

    with pytest.raises(InsufficientBalanceError):
        draw_game_gacha(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            draw_count=1,
        )

    assert user.balance == 29
    assert unit_of_work.assets.assets == []
    unit_of_work.commit.assert_not_called()


def test_game_gacha_multi_draw_charges_300_and_returns_duplicate_coin_rewards() -> None:
    user = _user(balance=1_000)
    unit_of_work = _unit_of_work(user)
    unit_of_work.assets = FakeAssetRepository(
        [
            Asset(
                id=1,
                public_id=uuid.uuid4(),
                user_id=user.id,
                cat_id=2,
                item_id=None,
                quantity=1,
            )
        ]
    )
    source = MagicMock()
    source.random.return_value = 0.01
    request_id = uuid.uuid4()

    result = draw_game_gacha(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=request_id,
        draw_count=11,
        random_source=source,
    )

    assert len(result["rewards"]) == 11
    assert all(reward["exchange_coins"] == 15 for reward in result["rewards"])
    assert result["remaining_balance"] == 865
    assert user.balance == 865
    execution = unit_of_work.executions.executions[request_id]
    assert execution.balance_cost == 300


def test_game_gacha_multi_draw_requires_full_300_balance_before_rewards() -> None:
    user = _user(balance=299)
    unit_of_work = _unit_of_work(user)

    with pytest.raises(InsufficientBalanceError):
        draw_game_gacha(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            draw_count=11,
        )

    assert user.balance == 299
    unit_of_work.commit.assert_not_called()
