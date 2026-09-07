import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import InvalidItemCategoryError, ResourceNotFoundError
from app.models.asset import Asset
from app.models.cat import Cat
from app.models.item import Item
from app.models.user import User
from app.modules.shop.consumables import use_consumable
from tests.fakes.repositories import (
    FakeAssetRepository,
    FakeCatRepository,
    FakeExecutionRepository,
    FakeItemRepository,
    FakeUserRepository,
)


def build_case(*, quantity: int = 2, category: str = "CONSUMABLE"):
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="care@example.com",
        username="care-user",
        role="STUDENT",
        balance=1_000,
        mileage=0,
        house_level=1,
        state_version=7,
    )
    item = Item(
        id=10,
        public_id=uuid.uuid4(),
        catalog_key="consumable.salmon-cubes",
        category=category,
        name="연어 큐브 간식",
        price=180,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        catalog_key="fluffy",
        name="복실이",
        persona="다정한 친구",
        rarity="COMMON",
    )
    assets = [
        Asset(id=1, public_id=uuid.uuid4(), user_id=user.id, cat_id=cat.id, item_id=None, quantity=1),
        Asset(id=2, public_id=uuid.uuid4(), user_id=user.id, cat_id=None, item_id=item.id, quantity=quantity),
    ]
    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository(assets)
    unit_of_work.executions = FakeExecutionRepository()
    return unit_of_work, user, item, cat


def test_use_consumable_decrements_one_and_is_idempotent() -> None:
    unit_of_work, user, item, cat = build_case()
    request_id = uuid.uuid4()

    first = use_consumable(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=request_id,
        item_public_id=item.public_id,
        cat_public_id=cat.public_id,
    )
    retry = use_consumable(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=request_id,
        item_public_id=item.public_id,
        cat_public_id=cat.public_id,
    )

    assert retry == first
    assert first["effect"] == "happy"
    assert first["remaining_quantity"] == 1
    assert unit_of_work.assets.get_item_asset_for_update(user.id, item.id).quantity == 1
    assert user.state_version == 8
    unit_of_work.commit.assert_called_once_with()


def test_use_consumable_removes_zero_quantity_asset() -> None:
    unit_of_work, user, item, cat = build_case(quantity=1)

    result = use_consumable(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=uuid.uuid4(),
        item_public_id=item.public_id,
        cat_public_id=cat.public_id,
    )

    assert result["remaining_quantity"] == 0
    assert unit_of_work.assets.get_item_asset_for_update(user.id, item.id) is None


def test_use_consumable_rejects_non_consumable_and_missing_inventory() -> None:
    unit_of_work, user, item, cat = build_case(category="FURNITURE")
    with pytest.raises(InvalidItemCategoryError):
        use_consumable(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            item_public_id=item.public_id,
            cat_public_id=cat.public_id,
        )

    unit_of_work, user, item, cat = build_case()
    unit_of_work.assets.assets = [asset for asset in unit_of_work.assets.assets if asset.item_id is None]
    with pytest.raises(ResourceNotFoundError):
        use_consumable(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            item_public_id=item.public_id,
            cat_public_id=cat.public_id,
        )
