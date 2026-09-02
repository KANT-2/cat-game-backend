import uuid

from app.models.cat import Cat
from app.models.item import Item
from app.models.user import User
from tests.fakes.repositories import (
    FakeAssetRepository,
    FakeCatMemoryRepository,
    FakeCatRepository,
    FakeItemRepository,
    FakePlacedObjectRepository,
    FakeUserRepository,
)


def test_fake_lookup_repositories() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="user@example.com",
        username="user",
        role="STUDENT",
        balance=100,
        mileage=0,
        house_level=1,
    )
    item = Item(
        id=2,
        public_id=uuid.uuid4(),
        category="FURNITURE",
        name="desk",
        price=50,
    )
    cat = Cat(
        id=3,
        public_id=uuid.uuid4(),
        name="nabi",
        persona="friendly",
        rarity="COMMON",
    )

    users = FakeUserRepository([user])
    items = FakeItemRepository([item])
    cats = FakeCatRepository([cat])

    assert users.get_by_public_id(user.public_id) is user
    assert users.get_for_update(user.id) is user
    assert items.get_by_public_id(item.public_id) is item
    assert cats.get_by_public_id(cat.public_id) is cat
    assert users.get_for_update(999) is None


def test_fake_asset_repository_grants_and_accumulates() -> None:
    repository = FakeAssetRepository()

    cat_asset = repository.grant_cat(user_id=1, cat_id=10)
    item_asset = repository.add_item_quantity(
        user_id=1,
        item_id=20,
        quantity=2,
    )
    same_item_asset = repository.add_item_quantity(
        user_id=1,
        item_id=20,
        quantity=3,
    )

    assert repository.get_cat_asset(1, 10) is cat_asset
    assert cat_asset.quantity == 1
    assert same_item_asset is item_asset
    assert item_asset.quantity == 5
    assert repository.get_item_asset_for_update(1, 20) is item_asset


def test_fake_placed_object_repository_counts_and_adds() -> None:
    repository = FakePlacedObjectRepository()

    placed = repository.add(
        user_id=1,
        item_id=20,
        position_data={"x": 10, "y": 20},
    )

    assert repository.count_for_update(1, 20) == 1
    assert repository.count_for_update(2, 20) == 0
    assert placed.position_data == {"x": 10, "y": 20}


def test_fake_cat_memory_repository_accumulates() -> None:
    repository = FakeCatMemoryRepository()

    first = repository.add(10, "첫 번째 대화")
    second = repository.add(10, "두 번째 대화")
    repository.add(20, "다른 고양이 대화")

    assert repository.list_by_user_cat_id(10) == [first, second]