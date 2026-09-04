import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import (
    IdempotencyConflictError,
    InsufficientBalanceError,
    InvalidQuantityError,
    ResourceNotFoundError,
)
from app.models.asset import Asset
from app.models.cat import Cat
from app.models.user import User
from app.modules.gacha.policy import GachaPolicy, GachaReward
from app.modules.gacha.service import draw_cats
from tests.fakes.repositories import (
    FakeAssetRepository,
    FakeCatRepository,
    FakeExecutionRepository,
    FakeUserRepository,
)


def test_draw_cats_grants_new_cat_in_one_transaction() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="gacha@example.com",
        username="gacha-user",
        role="STUDENT",
        balance=1000,
        mileage=10,
        house_level=1,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="Nabi",
        persona="Friendly",
        rarity="COMMON",
    )
    request_id = uuid.uuid4()

    policy = MagicMock(spec=GachaPolicy)
    policy.calculate_balance_cost.return_value = 200
    policy.draw.return_value = [
        GachaReward(
            cat_public_id=cat.public_id,
            duplicate_mileage=25,
        )
    ]

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    result = draw_cats(
        unit_of_work=unit_of_work,
        policy=policy,
        user_public_id=user.public_id,
        request_id=request_id,
        draw_count=1,
    )

    asset = unit_of_work.assets.get_cat_asset(user.id, cat.id)
    execution = unit_of_work.executions.executions[request_id]

    assert user.balance == 800
    assert user.mileage == 10
    assert asset is not None
    assert asset.quantity == 1

    assert result == {
        "execution_public_id": str(execution.public_id),
        "request_id": str(request_id),
        "draw_count": 1,
        "bonus_draw_count": 0,
        "balance_cost": 200,
        "balance": 800,
        "mileage": 10,
        "results": [
            {
                "cat_public_id": str(cat.public_id),
                "name": "Nabi",
                "rarity": "COMMON",
                "is_duplicate": False,
                "mileage_awarded": 0,
            }
        ],
    }

    assert execution.draw_count == 1
    assert execution.balance_cost == 200
    assert execution.result_data == result
    policy.calculate_balance_cost.assert_called_once_with(draw_count=1)
    policy.draw.assert_called_once_with(draw_count=1)
    unit_of_work.commit.assert_called_once_with()


def test_draw_cats_converts_duplicate_cat_to_mileage() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="duplicate@example.com",
        username="duplicate-user",
        role="STUDENT",
        balance=1000,
        mileage=10,
        house_level=1,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="Nabi",
        persona="Friendly",
        rarity="COMMON",
    )
    existing_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=cat.id,
        item_id=None,
        quantity=1,
    )
    request_id = uuid.uuid4()

    policy = MagicMock(spec=GachaPolicy)
    policy.calculate_balance_cost.return_value = 200
    policy.draw.return_value = [
        GachaReward(
            cat_public_id=cat.public_id,
            duplicate_mileage=25,
        )
    ]

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository([existing_asset])
    unit_of_work.executions = FakeExecutionRepository()

    result = draw_cats(
        unit_of_work=unit_of_work,
        policy=policy,
        user_public_id=user.public_id,
        request_id=request_id,
        draw_count=1,
    )

    assert user.balance == 800
    assert user.mileage == 35
    assert len(unit_of_work.assets.assets) == 1
    assert existing_asset.quantity == 1
    assert result["mileage"] == 35
    assert result["results"] == [
        {
            "cat_public_id": str(cat.public_id),
            "name": "Nabi",
            "rarity": "COMMON",
            "is_duplicate": True,
            "mileage_awarded": 25,
        }
    ]
    unit_of_work.commit.assert_called_once_with()


def test_draw_cats_reuses_completed_result_without_drawing_twice() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="retry-gacha@example.com",
        username="retry-gacha-user",
        role="STUDENT",
        balance=1000,
        mileage=10,
        house_level=1,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="Nabi",
        persona="Friendly",
        rarity="COMMON",
    )
    request_id = uuid.uuid4()

    policy = MagicMock(spec=GachaPolicy)
    policy.calculate_balance_cost.return_value = 200
    policy.draw.return_value = [
        GachaReward(
            cat_public_id=cat.public_id,
            duplicate_mileage=25,
        )
    ]

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    first_result = draw_cats(
        unit_of_work=unit_of_work,
        policy=policy,
        user_public_id=user.public_id,
        request_id=request_id,
        draw_count=1,
    )
    retry_result = draw_cats(
        unit_of_work=unit_of_work,
        policy=policy,
        user_public_id=user.public_id,
        request_id=request_id,
        draw_count=1,
    )

    asset = unit_of_work.assets.get_cat_asset(user.id, cat.id)

    assert retry_result == first_result
    assert user.balance == 800
    assert user.mileage == 10
    assert asset is not None
    assert asset.quantity == 1
    assert len(unit_of_work.assets.assets) == 1
    policy.calculate_balance_cost.assert_called_once_with(draw_count=1)
    policy.draw.assert_called_once_with(draw_count=1)
    unit_of_work.commit.assert_called_once_with()


def test_draw_cats_rejects_same_request_id_with_different_draw_count() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="conflict-gacha@example.com",
        username="conflict-gacha-user",
        role="STUDENT",
        balance=1000,
        mileage=10,
        house_level=1,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="Nabi",
        persona="Friendly",
        rarity="COMMON",
    )
    request_id = uuid.uuid4()

    policy = MagicMock(spec=GachaPolicy)
    policy.calculate_balance_cost.return_value = 200
    policy.draw.return_value = [
        GachaReward(
            cat_public_id=cat.public_id,
            duplicate_mileage=25,
        )
    ]

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    draw_cats(
        unit_of_work=unit_of_work,
        policy=policy,
        user_public_id=user.public_id,
        request_id=request_id,
        draw_count=1,
    )

    with pytest.raises(
        IdempotencyConflictError,
        match="request_id conflict",
    ):
        draw_cats(
            unit_of_work=unit_of_work,
            policy=policy,
            user_public_id=user.public_id,
            request_id=request_id,
            draw_count=10,
        )

    assert user.balance == 800
    assert user.mileage == 10
    assert len(unit_of_work.assets.assets) == 1
    policy.calculate_balance_cost.assert_called_once_with(draw_count=1)
    policy.draw.assert_called_once_with(draw_count=1)
    unit_of_work.commit.assert_called_once_with()


def test_draw_cats_rejects_insufficient_balance_before_drawing() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="poor-gacha@example.com",
        username="poor-gacha-user",
        role="STUDENT",
        balance=100,
        mileage=10,
        house_level=1,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="Nabi",
        persona="Friendly",
        rarity="COMMON",
    )

    policy = MagicMock(spec=GachaPolicy)
    policy.calculate_balance_cost.return_value = 200
    policy.draw.return_value = [
        GachaReward(
            cat_public_id=cat.public_id,
            duplicate_mileage=25,
        )
    ]

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    with pytest.raises(
        InsufficientBalanceError,
        match="insufficient balance",
    ):
        draw_cats(
            unit_of_work=unit_of_work,
            policy=policy,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            draw_count=1,
        )

    assert user.balance == 100
    assert user.mileage == 10
    assert unit_of_work.assets.assets == []
    policy.draw.assert_not_called()
    unit_of_work.commit.assert_not_called()


@pytest.mark.parametrize("draw_count", [0, -1, 2, 11])
def test_draw_cats_rejects_unsupported_draw_count(
    draw_count: int,
) -> None:
    policy = MagicMock(spec=GachaPolicy)
    unit_of_work = MagicMock()

    with pytest.raises(
        InvalidQuantityError,
        match="draw_count must be 1 or 10",
    ):
        draw_cats(
            unit_of_work=unit_of_work,
            policy=policy,
            user_public_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            draw_count=draw_count,
        )

    unit_of_work.__enter__.assert_not_called()
    policy.calculate_balance_cost.assert_not_called()
    policy.draw.assert_not_called()


def test_draw_cats_rejects_same_request_id_from_different_user() -> None:
    first_user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="first-gacha@example.com",
        username="first-gacha-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    second_user = User(
        id=2,
        public_id=uuid.uuid4(),
        email="second-gacha@example.com",
        username="second-gacha-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="Nabi",
        persona="Friendly",
        rarity="COMMON",
    )
    request_id = uuid.uuid4()

    policy = MagicMock(spec=GachaPolicy)
    policy.calculate_balance_cost.return_value = 200
    policy.draw.return_value = [
        GachaReward(
            cat_public_id=cat.public_id,
            duplicate_mileage=25,
        )
    ]

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([first_user, second_user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    draw_cats(
        unit_of_work=unit_of_work,
        policy=policy,
        user_public_id=first_user.public_id,
        request_id=request_id,
        draw_count=1,
    )

    with pytest.raises(
        IdempotencyConflictError,
        match="request_id conflict",
    ):
        draw_cats(
            unit_of_work=unit_of_work,
            policy=policy,
            user_public_id=second_user.public_id,
            request_id=request_id,
            draw_count=1,
        )

    assert first_user.balance == 800
    assert second_user.balance == 1000
    assert len(unit_of_work.assets.assets) == 1
    policy.calculate_balance_cost.assert_called_once_with(draw_count=1)
    policy.draw.assert_called_once_with(draw_count=1)
    unit_of_work.commit.assert_called_once_with()


def test_draw_cats_rejects_wrong_number_of_policy_rewards() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="invalid-policy@example.com",
        username="invalid-policy-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="Nabi",
        persona="Friendly",
        rarity="COMMON",
    )

    policy = MagicMock(spec=GachaPolicy)
    policy.calculate_balance_cost.return_value = 200
    policy.draw.return_value = [
        GachaReward(
            cat_public_id=cat.public_id,
            duplicate_mileage=25,
        )
    ]

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    with pytest.raises(
        RuntimeError,
        match="gacha policy returned wrong reward count",
    ):
        draw_cats(
            unit_of_work=unit_of_work,
            policy=policy,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            draw_count=10,
        )

    assert user.balance == 1000
    assert user.mileage == 0
    assert unit_of_work.assets.assets == []
    unit_of_work.commit.assert_not_called()


def test_draw_cats_rejects_negative_policy_cost() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="negative-cost@example.com",
        username="negative-cost-user",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )

    policy = MagicMock(spec=GachaPolicy)
    policy.calculate_balance_cost.return_value = -1

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.executions = FakeExecutionRepository()

    with pytest.raises(
        RuntimeError,
        match="gacha policy returned negative balance cost",
    ):
        draw_cats(
            unit_of_work=unit_of_work,
            policy=policy,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            draw_count=1,
        )

    assert user.balance == 1000
    assert user.mileage == 0
    policy.draw.assert_not_called()
    unit_of_work.commit.assert_not_called()


def test_draw_cats_rejects_negative_duplicate_mileage() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="negative-mileage@example.com",
        username="negative-mileage-user",
        role="STUDENT",
        balance=1000,
        mileage=10,
        house_level=1,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="Nabi",
        persona="Friendly",
        rarity="COMMON",
    )
    existing_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=cat.id,
        item_id=None,
        quantity=1,
    )

    policy = MagicMock(spec=GachaPolicy)
    policy.calculate_balance_cost.return_value = 200
    policy.draw.return_value = [
        GachaReward(
            cat_public_id=cat.public_id,
            duplicate_mileage=-25,
        )
    ]

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository([existing_asset])
    unit_of_work.executions = FakeExecutionRepository()

    with pytest.raises(
        RuntimeError,
        match="gacha policy returned negative duplicate mileage",
    ):
        draw_cats(
            unit_of_work=unit_of_work,
            policy=policy,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            draw_count=1,
        )

    assert user.balance == 1000
    assert user.mileage == 10
    assert existing_asset.quantity == 1
    assert len(unit_of_work.assets.assets) == 1
    unit_of_work.commit.assert_not_called()


def test_draw_cats_handles_duplicate_within_same_multi_draw() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="multi-draw@example.com",
        username="multi-draw-user",
        role="STUDENT",
        balance=3000,
        mileage=10,
        house_level=1,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="Nabi",
        persona="Friendly",
        rarity="COMMON",
    )

    policy = MagicMock(spec=GachaPolicy)
    policy.calculate_balance_cost.return_value = 2000
    policy.draw.return_value = [
        GachaReward(
            cat_public_id=cat.public_id,
            duplicate_mileage=25,
        )
        for _ in range(11)
    ]

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    result = draw_cats(
        unit_of_work=unit_of_work,
        policy=policy,
        user_public_id=user.public_id,
        request_id=uuid.uuid4(),
        draw_count=10,
    )

    asset = unit_of_work.assets.get_cat_asset(user.id, cat.id)

    assert user.balance == 1000
    assert user.mileage == 260
    assert asset is not None
    assert asset.quantity == 1
    assert len(unit_of_work.assets.assets) == 1
    assert result["results"][0]["is_duplicate"] is False
    assert result["results"][0]["mileage_awarded"] == 0
    assert result["results"][1]["is_duplicate"] is True
    assert result["results"][1]["mileage_awarded"] == 25
    assert result["draw_count"] == 10
    assert result["bonus_draw_count"] == 1
    assert len(result["results"]) == 11
    assert all(draw["is_duplicate"] is True for draw in result["results"][1:])
    policy.calculate_balance_cost.assert_called_once_with(draw_count=10)
    policy.draw.assert_called_once_with(draw_count=11)
    unit_of_work.commit.assert_called_once_with()


def test_draw_cats_rejects_missing_user() -> None:
    policy = MagicMock(spec=GachaPolicy)

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository()
    unit_of_work.executions = FakeExecutionRepository()

    with pytest.raises(ResourceNotFoundError, match="user not found"):
        draw_cats(
            unit_of_work=unit_of_work,
            policy=policy,
            user_public_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            draw_count=1,
        )

    assert unit_of_work.executions.executions == {}
    policy.calculate_balance_cost.assert_not_called()
    policy.draw.assert_not_called()
    unit_of_work.commit.assert_not_called()


def test_draw_cats_rejects_unknown_policy_cat_before_charging() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="missing-cat@example.com",
        username="missing-cat-user",
        role="STUDENT",
        balance=1000,
        mileage=10,
        house_level=1,
    )

    policy = MagicMock(spec=GachaPolicy)
    policy.calculate_balance_cost.return_value = 200
    policy.draw.return_value = [
        GachaReward(
            cat_public_id=uuid.uuid4(),
            duplicate_mileage=25,
        )
    ]

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository()
    unit_of_work.assets = FakeAssetRepository()
    unit_of_work.executions = FakeExecutionRepository()

    with pytest.raises(ResourceNotFoundError, match="cat not found"):
        draw_cats(
            unit_of_work=unit_of_work,
            policy=policy,
            user_public_id=user.public_id,
            request_id=uuid.uuid4(),
            draw_count=1,
        )

    assert user.balance == 1000
    assert user.mileage == 10
    assert unit_of_work.assets.assets == []
    unit_of_work.commit.assert_not_called()
