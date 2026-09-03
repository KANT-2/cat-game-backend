import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import (
    ApplicationError,
    IdempotencyConflictError,
    ResourceNotFoundError,
)
from app.models.item import Item
from app.models.user import User
from app.models.user_cat import UserCat
from app.modules.shop.service import purchase_item
from tests.fakes.repositories import (
    FakeAssetRepository,
    FakeExecutionRepository,
    FakeItemRepository,
    FakeUserRepository,
)


def test_purchase_item_updates_everything_in_one_transaction() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="buyer@example.com",
        username="buyer",
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
    request_id = uuid.uuid4()

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    result = purchase_item(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=request_id,
        item_public_id=item.public_id,
        quantity=2,
    )

    asset = unit_of_work.assets.get_item_asset_for_update(user.id, item.id)
    execution = unit_of_work.executions.executions[request_id]

    assert user.balance == 700
    assert asset is not None
    assert asset.quantity == 2
    assert execution.balance_cost == 300
    assert execution.result_data == result
    assert result == {
        "execution_public_id": str(execution.public_id),
        "request_id": str(request_id),
        "item_public_id": str(item.public_id),
        "purchased_quantity": 2,
        "total_quantity": 2,
        "balance": 700,
    }
    unit_of_work.commit.assert_called_once_with()

def test_purchase_item_reuses_result_without_charging_twice() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="retry@example.com",
        username="retry-user",
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
    request_id = uuid.uuid4()

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    first_result = purchase_item(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=request_id,
        item_public_id=item.public_id,
        quantity=2,
    )
    retry_result = purchase_item(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=request_id,
        item_public_id=item.public_id,
        quantity=2,
    )

    asset = unit_of_work.assets.get_item_asset_for_update(user.id, item.id)

    assert retry_result == first_result
    assert user.balance == 700
    assert asset is not None
    assert asset.quantity == 2
    unit_of_work.commit.assert_called_once_with()

def test_purchase_item_rejects_same_request_id_with_different_quantity() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="conflict@example.com",
        username="conflict-user",
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
    request_id = uuid.uuid4()

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    purchase_item(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=request_id,
        item_public_id=item.public_id,
        quantity=1,
    )

    with pytest.raises(ApplicationError, match="request_id conflict"):
        purchase_item(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            request_id=request_id,
            item_public_id=item.public_id,
            quantity=2,
        )

    asset = unit_of_work.assets.get_item_asset_for_update(user.id, item.id)

    assert user.balance == 850
    assert asset is not None
    assert asset.quantity == 1
    unit_of_work.commit.assert_called_once_with()

def test_purchase_item_rejects_same_request_id_from_different_user() -> None:
    first_user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="first@example.com",
        username="first-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    second_user = User(
        id=2,
        public_id=uuid.uuid4(),
        email="second@example.com",
        username="second-user",
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
    request_id = uuid.uuid4()

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([first_user, second_user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    purchase_item(
        unit_of_work=unit_of_work,
        user_public_id=first_user.public_id,
        request_id=request_id,
        item_public_id=item.public_id,
        quantity=1,
    )

    with pytest.raises(IdempotencyConflictError, match="request_id conflict"):
        purchase_item(
            unit_of_work=unit_of_work,
            user_public_id=second_user.public_id,
            request_id=request_id,
            item_public_id=item.public_id,
            quantity=1,
        )

    first_asset = unit_of_work.assets.get_item_asset_for_update(
        first_user.id,
        item.id,
    )
    second_asset = unit_of_work.assets.get_item_asset_for_update(
        second_user.id,
        item.id,
    )

    assert first_user.balance == 850
    assert second_user.balance == 1000
    assert first_asset is not None
    assert first_asset.quantity == 1
    assert second_asset is None
    unit_of_work.commit.assert_called_once_with()

def test_purchase_item_rejects_insufficient_balance() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="poor@example.com",
        username="poor-user",
        role="STUDENT",
        balance=100,
        mileage=0,
        house_level=1,
    )
    item = Item(
        id=10,
        public_id=uuid.uuid4(),
        category="FURNITURE",
        name="Expensive Cat Chair",
        price=150,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    with pytest.raises(ApplicationError, match="insufficient balance"):
        purchase_item(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            item_public_id=item.public_id,
            quantity=1,
        )

    asset = unit_of_work.assets.get_item_asset_for_update(user.id, item.id)

    assert user.balance == 100
    assert asset is None
    unit_of_work.commit.assert_not_called()

@pytest.mark.parametrize("quantity", [0, -1])
def test_purchase_item_rejects_nonpositive_quantity(quantity: int) -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email=f"quantity-{quantity}@example.com",
        username=f"quantity-{quantity}",
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
    unit_of_work.executions = FakeExecutionRepository()

    with pytest.raises(ApplicationError, match="quantity must be positive"):
        purchase_item(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            item_public_id=item.public_id,
            quantity=quantity,
        )

    assert user.balance == 1000
    assert unit_of_work.assets.assets == []
    assert unit_of_work.executions.executions == {}
    unit_of_work.commit.assert_not_called()

def test_purchase_item_rejects_missing_user() -> None:
    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository()
    unit_of_work.executions = FakeExecutionRepository()

    with pytest.raises(ApplicationError, match="user not found"):
        purchase_item(
            unit_of_work=unit_of_work,
            user_public_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            item_public_id=uuid.uuid4(),
            quantity=1,
        )

    assert unit_of_work.executions.executions == {}
    unit_of_work.commit.assert_not_called()

def test_purchase_item_rejects_missing_item() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="missing-item@example.com",
        username="missing-item-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository()
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    with pytest.raises(ResourceNotFoundError, match="item not found"):
        purchase_item(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            item_public_id=uuid.uuid4(),
            quantity=1,
        )

    assert user.balance == 1000
    assert unit_of_work.assets.assets == []
    unit_of_work.commit.assert_not_called()

def test_purchase_item_adds_quantity_to_existing_asset() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="existing@example.com",
        username="existing-user",
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
    existing_asset = UserCat(
        id=20,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=None,
        item_id=item.id,
        quantity=3,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.items = FakeItemRepository([item])
    unit_of_work.assets = FakeAssetRepository([existing_asset])
    unit_of_work.executions = FakeExecutionRepository()

    result = purchase_item(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=uuid.uuid4(),
        item_public_id=item.public_id,
        quantity=2,
    )

    assert user.balance == 700
    assert len(unit_of_work.assets.assets) == 1
    assert existing_asset.quantity == 5
    assert result["purchased_quantity"] == 2
    assert result["total_quantity"] == 5
    unit_of_work.commit.assert_called_once_with()