import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import (
    InvalidItemCategoryError,
    ResourceNotFoundError,
)
from app.models.asset import Asset
from app.models.item import Item
from app.models.user import User
from app.modules.housing.service import apply_surface_item
from tests.fakes.repositories import (
    FakeAssetRepository,
    FakeItemRepository,
    FakeUserRepository,
)


def test_apply_surface_item_sets_owned_wallpaper_in_one_transaction() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="wallpaper@example.com",
        username="wallpaper-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
        wallpaper_item_id=None,
        floor_item_id=None,
    )
    wallpaper = Item(
        id=10,
        public_id=uuid.uuid4(),
        category="WALLPAPER",
        name="Cloud Wallpaper",
        price=150,
    )
    asset = Asset(
        id=20,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=None,
        item_id=wallpaper.id,
        quantity=1,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([wallpaper])
    unit_of_work.assets = FakeAssetRepository([asset])

    result = apply_surface_item(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        item_public_id=wallpaper.public_id,
    )

    assert user.wallpaper_item_id == wallpaper.id
    assert user.floor_item_id is None
    assert result.user_public_id == user.public_id
    assert result.item_public_id == wallpaper.public_id
    assert result.category == "WALLPAPER"
    assert "id" not in result.model_dump()
    assert "wallpaper_item_id" not in result.model_dump()
    unit_of_work.commit.assert_called_once_with()

def test_apply_surface_item_sets_owned_floor_without_changing_wallpaper() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="floor@example.com",
        username="floor-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
        wallpaper_item_id=99,
        floor_item_id=None,
    )
    floor = Item(
        id=10,
        public_id=uuid.uuid4(),
        category="FLOOR",
        name="Wood Floor",
        price=150,
    )
    asset = Asset(
        id=20,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=None,
        item_id=floor.id,
        quantity=1,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([floor])
    unit_of_work.assets = FakeAssetRepository([asset])

    result = apply_surface_item(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        item_public_id=floor.public_id,
    )

    assert user.wallpaper_item_id == 99
    assert user.floor_item_id == floor.id
    assert result.user_public_id == user.public_id
    assert result.item_public_id == floor.public_id
    assert result.category == "FLOOR"
    unit_of_work.commit.assert_called_once_with()

def test_apply_surface_item_rejects_furniture_category() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="surface-category@example.com",
        username="surface-category-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
        wallpaper_item_id=None,
        floor_item_id=None,
    )
    furniture = Item(
        id=10,
        public_id=uuid.uuid4(),
        category="FURNITURE",
        name="Cat Chair",
        price=150,
    )
    asset = Asset(
        id=20,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=None,
        item_id=furniture.id,
        quantity=1,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([furniture])
    unit_of_work.assets = FakeAssetRepository([asset])

    with pytest.raises(
        InvalidItemCategoryError,
        match="item is not wallpaper or floor",
    ):
        apply_surface_item(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            item_public_id=furniture.public_id,
        )

    assert user.wallpaper_item_id is None
    assert user.floor_item_id is None
    unit_of_work.commit.assert_not_called()

def test_apply_surface_item_rejects_unowned_surface() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="unowned-surface@example.com",
        username="unowned-surface-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
        wallpaper_item_id=None,
        floor_item_id=None,
    )
    wallpaper = Item(
        id=10,
        public_id=uuid.uuid4(),
        category="WALLPAPER",
        name="Cloud Wallpaper",
        price=150,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([wallpaper])
    unit_of_work.assets = FakeAssetRepository()

    with pytest.raises(
        ResourceNotFoundError,
        match="item asset not found",
    ):
        apply_surface_item(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            item_public_id=wallpaper.public_id,
        )

    assert user.wallpaper_item_id is None
    assert user.floor_item_id is None
    unit_of_work.commit.assert_not_called()

def test_apply_surface_item_rejects_missing_user() -> None:
    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository()

    with pytest.raises(
        ResourceNotFoundError,
        match="user not found",
    ):
        apply_surface_item(
            unit_of_work=unit_of_work,
            user_public_id=uuid.uuid4(),
            item_public_id=uuid.uuid4(),
        )

    unit_of_work.commit.assert_not_called()

def test_apply_surface_item_rejects_missing_item() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="missing-surface@example.com",
        username="missing-surface-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
        wallpaper_item_id=None,
        floor_item_id=None,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository()

    with pytest.raises(
        ResourceNotFoundError,
        match="item not found",
    ):
        apply_surface_item(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            item_public_id=uuid.uuid4(),
        )

    assert user.wallpaper_item_id is None
    assert user.floor_item_id is None
    unit_of_work.commit.assert_not_called()