import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import (
    InvalidItemCategoryError,
    PlacementLimitExceededError,
    ResourceNotFoundError,
)
from app.models.item import Item
from app.models.placed_object import PlacedObject
from app.models.user import User
from app.models.user_cat import UserCat
from app.modules.housing.service import (
    place_furniture,
    remove_furniture_placement,
    update_furniture_placement,
)
from app.schemas.placed_object import PositionData
from tests.fakes.repositories import (
    FakeAssetRepository,
    FakeItemRepository,
    FakePlacedObjectRepository,
    FakeUserRepository,
)


def test_place_furniture_uses_owned_quantity_in_one_transaction() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="housing@example.com",
        username="housing-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    item = Item(
        id=10,
        public_id=uuid.uuid4(),
        category="FURNITURE",
        name="Cat Chair",
        price=150,
    )
    asset = UserCat(
        id=20,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=None,
        item_id=item.id,
        quantity=2,
    )
    position_data = PositionData(
        x=120,
        y=80,
        rotation=45,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.assets = FakeAssetRepository([asset])
    unit_of_work.placed_objects = FakePlacedObjectRepository()

    result = place_furniture(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        item_public_id=item.public_id,
        position_data=position_data,
    )

    assert len(unit_of_work.placed_objects.placed_objects) == 1

    placed_object = unit_of_work.placed_objects.placed_objects[0]

    assert result.public_id == placed_object.public_id
    assert result.item_public_id == item.public_id
    assert result.position_data == {
        "x": 120.0,
        "y": 80.0,
        "rotation": 45.0,
    }
    assert "id" not in result.model_dump()
    assert "user_id" not in result.model_dump()
    assert "item_id" not in result.model_dump()
    unit_of_work.commit.assert_called_once_with()

def test_place_furniture_rejects_non_furniture_item() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="wallpaper@example.com",
        username="wallpaper-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    item = Item(
        id=10,
        public_id=uuid.uuid4(),
        category="WALLPAPER",
        name="Cloud Wallpaper",
        price=150,
    )
    asset = UserCat(
        id=20,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=None,
        item_id=item.id,
        quantity=1,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.assets = FakeAssetRepository([asset])
    unit_of_work.placed_objects = FakePlacedObjectRepository()

    with pytest.raises(
        InvalidItemCategoryError,
        match="item is not furniture",
    ):
        place_furniture(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            item_public_id=item.public_id,
            position_data=PositionData(
                x=120,
                y=80,
                rotation=45,
            ),
        )

    assert unit_of_work.placed_objects.placed_objects == []
    unit_of_work.commit.assert_not_called()

def test_place_furniture_rejects_more_than_owned_quantity() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="placement-limit@example.com",
        username="placement-limit-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    item = Item(
        id=10,
        public_id=uuid.uuid4(),
        category="FURNITURE",
        name="Cat Chair",
        price=150,
    )
    asset = UserCat(
        id=20,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=None,
        item_id=item.id,
        quantity=1,
    )
    existing_placement = PlacedObject(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        item_id=item.id,
        position_data={
            "x": 10,
            "y": 20,
            "rotation": 0,
        },
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.assets = FakeAssetRepository([asset])
    unit_of_work.placed_objects = FakePlacedObjectRepository(
        [existing_placement]
    )

    with pytest.raises(
        PlacementLimitExceededError,
        match="placement exceeds owned quantity",
    ):
        place_furniture(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            item_public_id=item.public_id,
            position_data=PositionData(
                x=120,
                y=80,
                rotation=45,
            ),
        )

    assert unit_of_work.placed_objects.placed_objects == [
        existing_placement
    ]
    unit_of_work.commit.assert_not_called()

def test_place_furniture_rejects_unowned_item() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="unowned@example.com",
        username="unowned-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    item = Item(
        id=10,
        public_id=uuid.uuid4(),
        category="FURNITURE",
        name="Cat Chair",
        price=150,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.placed_objects = FakePlacedObjectRepository()

    with pytest.raises(
        ResourceNotFoundError,
        match="item asset not found",
    ):
        place_furniture(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            item_public_id=item.public_id,
            position_data=PositionData(
                x=120,
                y=80,
                rotation=45,
            ),
        )

    assert unit_of_work.placed_objects.placed_objects == []
    unit_of_work.commit.assert_not_called()

def test_update_furniture_placement_changes_only_position() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="move@example.com",
        username="move-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    item = Item(
        id=10,
        public_id=uuid.uuid4(),
        category="FURNITURE",
        name="Cat Chair",
        price=150,
    )
    placed_object = PlacedObject(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        item_id=item.id,
        position_data={
            "x": 10,
            "y": 20,
            "rotation": 0,
        },
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.placed_objects = FakePlacedObjectRepository(
        [placed_object]
    )

    result = update_furniture_placement(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        placed_object_public_id=placed_object.public_id,
        position_data=PositionData(
            x=300,
            y=150,
            rotation=90,
        ),
    )

    assert placed_object.position_data == {
        "x": 300.0,
        "y": 150.0,
        "rotation": 90.0,
    }
    assert result.public_id == placed_object.public_id
    assert result.item_public_id == item.public_id
    assert result.position_data == placed_object.position_data
    assert "id" not in result.model_dump()
    assert "user_id" not in result.model_dump()
    assert "item_id" not in result.model_dump()
    unit_of_work.commit.assert_called_once_with()

def test_update_furniture_placement_hides_other_users_object() -> None:
    owner = User(
        id=1,
        public_id=uuid.uuid4(),
        email="owner@example.com",
        username="owner",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    attacker = User(
        id=2,
        public_id=uuid.uuid4(),
        email="attacker@example.com",
        username="attacker",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    placed_object = PlacedObject(
        id=30,
        public_id=uuid.uuid4(),
        user_id=owner.id,
        item_id=10,
        position_data={
            "x": 10,
            "y": 20,
            "rotation": 0,
        },
    )
    original_position = dict(placed_object.position_data)

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([owner, attacker])
    unit_of_work.placed_objects = FakePlacedObjectRepository(
        [placed_object]
    )

    with pytest.raises(
        ResourceNotFoundError,
        match="placed object not found",
    ):
        update_furniture_placement(
            unit_of_work=unit_of_work,
            user_public_id=attacker.public_id,
            placed_object_public_id=placed_object.public_id,
            position_data=PositionData(
                x=300,
                y=150,
                rotation=90,
            ),
        )

    assert placed_object.position_data == original_position
    unit_of_work.commit.assert_not_called()

def test_remove_furniture_placement_keeps_owned_quantity() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="remove@example.com",
        username="remove-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    item = Item(
        id=10,
        public_id=uuid.uuid4(),
        category="FURNITURE",
        name="Cat Chair",
        price=150,
    )
    asset = UserCat(
        id=20,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=None,
        item_id=item.id,
        quantity=2,
    )
    placed_object = PlacedObject(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        item_id=item.id,
        position_data={
            "x": 10,
            "y": 20,
            "rotation": 0,
        },
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.assets = FakeAssetRepository([asset])
    unit_of_work.placed_objects = FakePlacedObjectRepository(
        [placed_object]
    )

    result = remove_furniture_placement(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        placed_object_public_id=placed_object.public_id,
    )

    assert result is None
    assert unit_of_work.placed_objects.placed_objects == []
    assert asset.quantity == 2
    assert unit_of_work.assets.assets == [asset]
    unit_of_work.commit.assert_called_once_with()

def test_remove_furniture_placement_hides_other_users_object() -> None:
    owner = User(
        id=1,
        public_id=uuid.uuid4(),
        email="remove-owner@example.com",
        username="remove-owner",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    attacker = User(
        id=2,
        public_id=uuid.uuid4(),
        email="remove-attacker@example.com",
        username="remove-attacker",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    placed_object = PlacedObject(
        id=30,
        public_id=uuid.uuid4(),
        user_id=owner.id,
        item_id=10,
        position_data={
            "x": 10,
            "y": 20,
            "rotation": 0,
        },
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([owner, attacker])
    unit_of_work.placed_objects = FakePlacedObjectRepository(
        [placed_object]
    )

    with pytest.raises(
        ResourceNotFoundError,
        match="placed object not found",
    ):
        remove_furniture_placement(
            unit_of_work=unit_of_work,
            user_public_id=attacker.public_id,
            placed_object_public_id=placed_object.public_id,
        )

    assert unit_of_work.placed_objects.placed_objects == [
        placed_object
    ]
    unit_of_work.commit.assert_not_called()