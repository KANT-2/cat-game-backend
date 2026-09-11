import uuid
from unittest.mock import Mock

import pytest

from app.modules.game.catalog import ITEM_DEFINITIONS
from app.modules.game.gacha import _REWARDS, _draw_reward, draw_game_gacha
from tests.unit.modules.game.test_game_gacha import _unit_of_work, _user


def test_pool_covers_all_furniture_and_no_single_purchase_or_consumable_items():
    expected = {item.catalog_key for item in ITEM_DEFINITIONS if item.category == "FURNITURE"}
    assert {r.catalog_key for r in _REWARDS if r.kind == "furniture"} == expected
    assert len(_REWARDS) == len(expected) + 5
    assert sum(r.weight for r in _REWARDS) == pytest.approx(1)
    assert [(reward.catalog_key, reward.weight) for reward in _REWARDS[:5]] == [
        ("ink", 0.05),
        ("silver", 0.01),
        ("calico", 0.01),
        ("tuxedo", 0.01),
        ("fold", 0.01),
    ]
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
        uow.items.items = []
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
        granted_item = uow.items.get_by_catalog_key(definition.catalog_key)
        assert granted_item is not None
        assert uow.assets.assets[0].item_id == granted_item.id
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


def test_draw_repairs_an_unseeded_expanded_catalog_before_charging():
    definition = next(
        reward for reward in _REWARDS if reward.catalog_key == "furniture.ocean.rug"
    )
    boundary = sum(reward.weight for reward in _REWARDS[: _REWARDS.index(definition)])
    source = Mock()
    source.random.return_value = boundary + definition.weight / 2
    user = _user()
    uow = _unit_of_work(user)
    assert uow.items.get_by_catalog_key(definition.catalog_key) is None

    result = draw_game_gacha(
        unit_of_work=uow,
        user_public_id=user.public_id,
        request_id=uuid.uuid4(),
        draw_count=1,
        random_source=source,
    )

    assert result["rewards"][0]["shop_item_id"] == definition.catalog_key
    assert uow.items.get_by_catalog_key(definition.catalog_key) is not None
    assert user.balance == 70
