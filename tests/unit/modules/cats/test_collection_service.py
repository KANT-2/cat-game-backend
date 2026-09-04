import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ResourceNotFoundError
from app.models.asset import Asset
from app.models.cat import Cat
from app.models.user import User
from app.modules.cats.service import get_cat_collection
from tests.fakes.repositories import (
    FakeAssetRepository,
    FakeCatRepository,
    FakeUserRepository,
)


def test_get_cat_collection_returns_owned_and_unowned_cats() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="collector@example.com",
        username="collector",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    owned_cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="나비",
        persona="차분하고 다정한 고양이",
        rarity="COMMON",
    )
    unowned_cat = Cat(
        id=21,
        public_id=uuid.uuid4(),
        name="별이",
        persona="호기심 많은 고양이",
        rarity="RARE",
    )
    owned_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=owned_cat.id,
        item_id=None,
        quantity=1,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([unowned_cat, owned_cat])
    unit_of_work.assets = FakeAssetRepository([owned_asset])

    result = get_cat_collection(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
    )

    assert result.total_count == 2
    assert result.owned_count == 1
    assert [cat.name for cat in result.cats] == ["나비", "별이"]
    assert result.cats[0].is_owned is True
    assert result.cats[0].cat_asset_public_id == owned_asset.public_id
    assert result.cats[1].is_owned is False
    assert result.cats[1].cat_asset_public_id is None

    forbidden = {"id", "user_id", "cat_id", "asset_id"}
    dumped = result.model_dump()
    assert forbidden.isdisjoint(dumped)
    for cat in dumped["cats"]:
        assert forbidden.isdisjoint(cat)

    unit_of_work.commit.assert_not_called()


def test_get_cat_collection_rejects_unknown_user() -> None:
    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository()
    unit_of_work.cats = FakeCatRepository()
    unit_of_work.assets = FakeAssetRepository()

    with pytest.raises(ResourceNotFoundError, match="user not found"):
        get_cat_collection(
            unit_of_work=unit_of_work,
            user_public_id=uuid.uuid4(),
        )

    unit_of_work.commit.assert_not_called()
