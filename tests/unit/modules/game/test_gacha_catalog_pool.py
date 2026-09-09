import uuid
from unittest.mock import Mock

import pytest

from app.models.item import Item
from app.modules.game.catalog import ITEM_DEFINITIONS
from app.modules.game.gacha import _REWARDS, _draw_reward, draw_game_gacha
from tests.unit.modules.game.test_game_gacha import _unit_of_work, _user


def test_pool_covers_all_furniture_and_no_single_purchase_or_consumable_items():
    expected = {item.catalog_key for item in ITEM_DEFINITIONS if item.category == "FURNITURE"}
    assert {r.catalog_key for r in _REWARDS if r.kind == "furniture"} == expected
    assert len(_REWARDS) == len(expected) + 1
    assert sum(r.weight for r in _REWARDS) == pytest.approx(1)
    assert _REWARDS[0].catalog_key == "ink"
    assert _REWARDS[0].weight == 0.05
    for theme in ("forest", "alley", "room", "desk-theme", "ocean"):
        assert any(f"furniture.{theme}." in key for key in expected)


def test_each_pool_interval_grants_the_exact_catalog_item_and_charges_once():
    boundary = 0
    for definition in _REWARDS:
        roll = boundary + definition.weight / 2
        boundary += definition.weight
        assert _draw_reward(roll) == definition
        if definition.kind == "cat":
            continue
        user = _user()
        uow = _unit_of_work(user)
        uow.items.items.append(
            Item(
                id=100,
                public_id=uuid.uuid4(),
                catalog_key=definition.catalog_key,
                category="FURNITURE",
                name="test",
                price=100,
            )
        )
        # Replace the fixture's old item to keep catalog keys unique.
        uow.items.items = [uow.items.items[-1]]
        source = Mock()
        source.random.return_value = roll
        request_id = uuid.uuid4()
        result = draw_game_gacha(
            unit_of_work=uow,
            user_public_id=user.public_id,
            request_id=request_id,
            draw_count=1,
            random_source=source,
        )
        assert result["rewards"][0]["shop_item_id"] == definition.catalog_key
        assert user.balance == 70
        assert uow.assets.assets[0].item_id == 100
        assert uow.assets.assets[0].quantity == 1
        assert (
            draw_game_gacha(
                unit_of_work=uow,
                user_public_id=user.public_id,
                request_id=request_id,
                draw_count=1,
                random_source=source,
            )
            == result
        )
        assert user.balance == 70
