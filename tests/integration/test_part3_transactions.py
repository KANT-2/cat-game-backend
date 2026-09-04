import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import (
    IdempotencyConflictError,
    InsufficientBalanceError,
    PlacementLimitExceededError,
)
from app.db.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyExecutionRepository,
)
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.models.asset import Asset
from app.models.cat import Cat
from app.models.gacha_execution import GachaExecution
from app.models.item import Item
from app.models.placed_object import PlacedObject
from app.models.user import User
from app.modules.gacha.policy import GachaReward
from app.modules.gacha.service import draw_cats
from app.modules.housing.service import (
    apply_surface_item,
    place_furniture,
)
from app.modules.shop.service import purchase_item
from app.schemas.placed_object import PositionData


def test_purchase_rolls_back_all_changes_on_mid_transaction_failure(
    db_session,
    monkeypatch,
) -> None:
    user = User(
        email=f"rollback-{uuid.uuid4()}@example.com",
        username=f"rollback-user-{uuid.uuid4()}",
        balance=1000,
    )
    item = Item(
        name=f"rollback-item-{uuid.uuid4()}",
        category="FURNITURE",
        price=300,
    )
    db_session.add_all([user, item])
    db_session.flush()

    user_id = user.id
    user_public_id = user.public_id
    item_public_id = item.public_id
    request_id = uuid.uuid4()

    original_add_item_quantity = SqlAlchemyAssetRepository.add_item_quantity

    def fail_after_asset_mutation(
        repository,
        user_id: int,
        item_id: int,
        quantity: int,
    ) -> None:
        original_add_item_quantity(
            repository,
            user_id,
            item_id,
            quantity,
        )
        repository._session.flush()
        raise RuntimeError("forced failure after asset mutation")

    monkeypatch.setattr(
        SqlAlchemyAssetRepository,
        "add_item_quantity",
        fail_after_asset_mutation,
    )

    session_factory = sessionmaker(
        bind=db_session.connection(),
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    unit_of_work = SqlAlchemyUnitOfWork(session_factory=session_factory)

    with pytest.raises(
        RuntimeError,
        match="forced failure after asset mutation",
    ):
        purchase_item(
            unit_of_work=unit_of_work,
            user_public_id=user_public_id,
            item_public_id=item_public_id,
            quantity=1,
            request_id=request_id,
        )

    db_session.expire_all()

    persisted_user = db_session.get(User, user_id)
    asset_count = db_session.scalar(
        select(func.count()).select_from(Asset).where(Asset.user_id == user_id)
    )
    execution = db_session.scalar(
        select(GachaExecution).where(GachaExecution.request_id == request_id)
    )

    assert persisted_user is not None
    assert persisted_user.balance == 1000
    assert asset_count == 0
    assert execution is None


def test_concurrent_same_purchase_request_charges_and_grants_once(
    engine,
) -> None:
    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    user = User(
        email=f"concurrent-{uuid.uuid4()}@example.com",
        username=f"concurrent-user-{uuid.uuid4()}",
        balance=1000,
    )
    item = Item(
        name=f"concurrent-item-{uuid.uuid4()}",
        category="FURNITURE",
        price=300,
    )

    with session_factory() as seed_session:
        seed_session.add_all([user, item])
        seed_session.commit()

    user_id = user.id
    item_id = item.id
    user_public_id = user.public_id
    item_public_id = item.public_id
    request_id = uuid.uuid4()
    start_barrier = Barrier(2)

    def purchase_once() -> dict[str, object]:
        start_barrier.wait()
        return purchase_item(
            unit_of_work=SqlAlchemyUnitOfWork(
                session_factory=session_factory,
            ),
            user_public_id=user_public_id,
            item_public_id=item_public_id,
            quantity=1,
            request_id=request_id,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(purchase_once),
                executor.submit(purchase_once),
            ]
            results = [future.result(timeout=10) for future in futures]

        with session_factory() as verification_session:
            persisted_user = verification_session.get(User, user_id)
            asset = verification_session.scalar(
                select(Asset).where(
                    Asset.user_id == user_id,
                    Asset.item_id == item_id,
                )
            )
            executions = verification_session.scalars(
                select(GachaExecution).where(GachaExecution.request_id == request_id)
            ).all()

        assert results[0] == results[1]
        assert persisted_user is not None
        assert persisted_user.balance == 700
        assert asset is not None
        assert asset.quantity == 1
        assert len(executions) == 1
        assert executions[0].status == "COMPLETED"
    finally:
        with session_factory() as cleanup_session:
            cleanup_session.execute(
                delete(GachaExecution).where(GachaExecution.request_id == request_id)
            )
            cleanup_session.execute(delete(Asset).where(Asset.user_id == user_id))
            cleanup_session.execute(delete(User).where(User.id == user_id))
            cleanup_session.execute(delete(Item).where(Item.id == item_id))
            cleanup_session.commit()


def test_concurrent_distinct_purchase_requests_do_not_overspend(
    engine,
) -> None:
    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    user = User(
        email=f"row-lock-{uuid.uuid4()}@example.com",
        username=f"row-lock-user-{uuid.uuid4()}",
        balance=500,
    )
    item = Item(
        name=f"row-lock-item-{uuid.uuid4()}",
        category="FURNITURE",
        price=300,
    )

    with session_factory() as seed_session:
        seed_session.add_all([user, item])
        seed_session.commit()

    user_id = user.id
    item_id = item.id
    user_public_id = user.public_id
    item_public_id = item.public_id
    request_ids = [uuid.uuid4(), uuid.uuid4()]
    start_barrier = Barrier(2)

    def purchase_once(
        request_id: uuid.UUID,
    ) -> tuple[str, dict[str, object] | None]:
        start_barrier.wait()

        try:
            result = purchase_item(
                unit_of_work=SqlAlchemyUnitOfWork(
                    session_factory=session_factory,
                ),
                user_public_id=user_public_id,
                item_public_id=item_public_id,
                quantity=1,
                request_id=request_id,
            )
        except InsufficientBalanceError:
            return "insufficient", None

        return "success", result

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(purchase_once, request_id) for request_id in request_ids]
            results = [future.result(timeout=10) for future in futures]

        with session_factory() as verification_session:
            persisted_user = verification_session.get(User, user_id)
            asset = verification_session.scalar(
                select(Asset).where(
                    Asset.user_id == user_id,
                    Asset.item_id == item_id,
                )
            )
            executions = verification_session.scalars(
                select(GachaExecution).where(GachaExecution.request_id.in_(request_ids))
            ).all()

        assert sorted(status for status, _ in results) == [
            "insufficient",
            "success",
        ]
        assert persisted_user is not None
        assert persisted_user.balance == 200
        assert asset is not None
        assert asset.quantity == 1
        assert len(executions) == 1
        assert executions[0].status == "COMPLETED"
    finally:
        with session_factory() as cleanup_session:
            cleanup_session.execute(
                delete(GachaExecution).where(GachaExecution.request_id.in_(request_ids))
            )
            cleanup_session.execute(delete(Asset).where(Asset.user_id == user_id))
            cleanup_session.execute(delete(User).where(User.id == user_id))
            cleanup_session.execute(delete(Item).where(Item.id == item_id))
            cleanup_session.commit()


def test_concurrent_gacha_requests_do_not_overspend(
    engine,
) -> None:
    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    user = User(
        email=f"gacha-lock-{uuid.uuid4()}@example.com",
        username=f"gacha-lock-user-{uuid.uuid4()}",
        balance=500,
    )
    cat = Cat(
        name=f"gacha-lock-cat-{uuid.uuid4()}",
        persona="Concurrency test cat",
        rarity="COMMON",
    )

    with session_factory() as seed_session:
        seed_session.add_all([user, cat])
        seed_session.commit()

    user_id = user.id
    cat_id = cat.id
    user_public_id = user.public_id
    cat_public_id = cat.public_id
    request_ids = [uuid.uuid4(), uuid.uuid4()]
    start_barrier = Barrier(2)

    class FixedPolicy:
        def calculate_balance_cost(
            self,
            *,
            draw_count: int,
        ) -> int:
            assert draw_count == 1
            return 300

        def draw(
            self,
            *,
            draw_count: int,
        ) -> list[GachaReward]:
            assert draw_count == 1
            return [
                GachaReward(
                    cat_public_id=cat_public_id,
                    duplicate_mileage=25,
                )
            ]

    policy = FixedPolicy()

    def draw_once(
        request_id: uuid.UUID,
    ) -> tuple[str, dict[str, object] | None]:
        start_barrier.wait()

        try:
            result = draw_cats(
                unit_of_work=SqlAlchemyUnitOfWork(
                    session_factory=session_factory,
                ),
                policy=policy,
                user_public_id=user_public_id,
                request_id=request_id,
                draw_count=1,
            )
        except InsufficientBalanceError:
            return "insufficient", None

        return "success", result

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(draw_once, request_id) for request_id in request_ids]
            results = [future.result(timeout=10) for future in futures]

        with session_factory() as verification_session:
            persisted_user = verification_session.get(User, user_id)
            asset = verification_session.scalar(
                select(Asset).where(
                    Asset.user_id == user_id,
                    Asset.cat_id == cat_id,
                )
            )
            executions = verification_session.scalars(
                select(GachaExecution).where(GachaExecution.request_id.in_(request_ids))
            ).all()

        assert sorted(status for status, _ in results) == [
            "insufficient",
            "success",
        ]
        assert persisted_user is not None
        assert persisted_user.balance == 200
        assert persisted_user.mileage == 0
        assert asset is not None
        assert asset.quantity == 1
        assert len(executions) == 1
        assert executions[0].status == "COMPLETED"
    finally:
        with session_factory() as cleanup_session:
            cleanup_session.execute(
                delete(GachaExecution).where(GachaExecution.request_id.in_(request_ids))
            )
            cleanup_session.execute(delete(Asset).where(Asset.user_id == user_id))
            cleanup_session.execute(delete(User).where(User.id == user_id))
            cleanup_session.execute(delete(Cat).where(Cat.id == cat_id))
            cleanup_session.commit()


def test_concurrent_purchase_and_surface_application_share_lock_order(
    engine,
) -> None:
    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    user = User(
        email=f"housing-lock-{uuid.uuid4()}@example.com",
        username=f"housing-lock-user-{uuid.uuid4()}",
        balance=1000,
    )
    item = Item(
        name=f"housing-lock-item-{uuid.uuid4()}",
        category="WALLPAPER",
        price=300,
    )

    with session_factory() as seed_session:
        seed_session.add_all([user, item])
        seed_session.flush()

        asset = Asset(
            user_id=user.id,
            item_id=item.id,
            quantity=1,
        )
        seed_session.add(asset)
        seed_session.commit()

    user_id = user.id
    item_id = item.id
    user_public_id = user.public_id
    item_public_id = item.public_id
    request_id = uuid.uuid4()
    start_barrier = Barrier(2)

    def purchase_once() -> dict[str, object]:
        start_barrier.wait()
        return purchase_item(
            unit_of_work=SqlAlchemyUnitOfWork(
                session_factory=session_factory,
            ),
            user_public_id=user_public_id,
            item_public_id=item_public_id,
            quantity=1,
            request_id=request_id,
        )

    def apply_surface_once() -> object:
        start_barrier.wait()
        return apply_surface_item(
            unit_of_work=SqlAlchemyUnitOfWork(
                session_factory=session_factory,
            ),
            user_public_id=user_public_id,
            item_public_id=item_public_id,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            purchase_future = executor.submit(purchase_once)
            surface_future = executor.submit(apply_surface_once)

            purchase_result = purchase_future.result(timeout=10)
            surface_result = surface_future.result(timeout=10)

        assert purchase_result["balance"] == 700
        assert surface_result.category == "WALLPAPER"

        with session_factory() as verification_session:
            persisted_user = verification_session.get(User, user_id)
            persisted_asset = verification_session.scalar(
                select(Asset).where(
                    Asset.user_id == user_id,
                    Asset.item_id == item_id,
                )
            )
            executions = verification_session.scalars(
                select(GachaExecution).where(GachaExecution.request_id == request_id)
            ).all()

            assert persisted_user is not None
            assert persisted_user.balance == 700
            assert persisted_user.wallpaper_item_id == item_id
            assert persisted_asset is not None
            assert persisted_asset.quantity == 2
            assert len(executions) == 1
            assert executions[0].status == "COMPLETED"
    finally:
        with session_factory() as cleanup_session:
            cleanup_session.execute(
                delete(GachaExecution).where(GachaExecution.request_id == request_id)
            )

            cleanup_user = cleanup_session.get(User, user_id)
            if cleanup_user is not None:
                cleanup_user.wallpaper_item_id = None
                cleanup_session.flush()

            cleanup_session.execute(delete(Asset).where(Asset.user_id == user_id))
            cleanup_session.execute(delete(User).where(User.id == user_id))
            cleanup_session.execute(delete(Item).where(Item.id == item_id))
            cleanup_session.commit()


def test_same_request_id_from_different_user_conflicts_in_postgresql(
    engine,
) -> None:
    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    first_user = User(
        email=f"first-request-owner-{uuid.uuid4()}@example.com",
        username=f"first-request-owner-{uuid.uuid4()}",
        balance=1000,
    )
    second_user = User(
        email=f"second-request-owner-{uuid.uuid4()}@example.com",
        username=f"second-request-owner-{uuid.uuid4()}",
        balance=1000,
    )
    item = Item(
        name=f"request-owner-item-{uuid.uuid4()}",
        category="FURNITURE",
        price=300,
    )

    with session_factory() as seed_session:
        seed_session.add_all([first_user, second_user, item])
        seed_session.commit()

    first_user_id = first_user.id
    second_user_id = second_user.id
    item_id = item.id
    request_id = uuid.uuid4()

    try:
        first_result = purchase_item(
            unit_of_work=SqlAlchemyUnitOfWork(
                session_factory=session_factory,
            ),
            user_public_id=first_user.public_id,
            item_public_id=item.public_id,
            quantity=1,
            request_id=request_id,
        )

        with pytest.raises(
            IdempotencyConflictError,
            match="request_id conflict",
        ):
            purchase_item(
                unit_of_work=SqlAlchemyUnitOfWork(
                    session_factory=session_factory,
                ),
                user_public_id=second_user.public_id,
                item_public_id=item.public_id,
                quantity=1,
                request_id=request_id,
            )

        assert first_result["balance"] == 700

        with session_factory() as verification_session:
            persisted_first_user = verification_session.get(
                User,
                first_user_id,
            )
            persisted_second_user = verification_session.get(
                User,
                second_user_id,
            )
            first_asset = verification_session.scalar(
                select(Asset).where(
                    Asset.user_id == first_user_id,
                    Asset.item_id == item_id,
                )
            )
            second_asset = verification_session.scalar(
                select(Asset).where(
                    Asset.user_id == second_user_id,
                    Asset.item_id == item_id,
                )
            )
            executions = verification_session.scalars(
                select(GachaExecution).where(GachaExecution.request_id == request_id)
            ).all()

            assert persisted_first_user is not None
            assert persisted_first_user.balance == 700
            assert persisted_second_user is not None
            assert persisted_second_user.balance == 1000
            assert first_asset is not None
            assert first_asset.quantity == 1
            assert second_asset is None
            assert len(executions) == 1
            assert executions[0].user_id == first_user_id
            assert executions[0].status == "COMPLETED"
    finally:
        with session_factory() as cleanup_session:
            cleanup_session.execute(
                delete(GachaExecution).where(GachaExecution.request_id == request_id)
            )
            cleanup_session.execute(
                delete(Asset).where(Asset.user_id.in_([first_user_id, second_user_id]))
            )
            cleanup_session.execute(
                delete(User).where(User.id.in_([first_user_id, second_user_id]))
            )
            cleanup_session.execute(delete(Item).where(Item.id == item_id))
            cleanup_session.commit()


def test_concurrent_furniture_placements_do_not_exceed_owned_quantity(
    engine,
) -> None:
    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    user = User(
        email=f"placement-lock-{uuid.uuid4()}@example.com",
        username=f"placement-lock-user-{uuid.uuid4()}",
        balance=0,
    )
    item = Item(
        name=f"placement-lock-item-{uuid.uuid4()}",
        category="FURNITURE",
        price=300,
    )

    with session_factory() as seed_session:
        seed_session.add_all([user, item])
        seed_session.flush()

        asset = Asset(
            user_id=user.id,
            item_id=item.id,
            quantity=1,
        )
        seed_session.add(asset)
        seed_session.commit()

    user_id = user.id
    item_id = item.id
    user_public_id = user.public_id
    item_public_id = item.public_id
    start_barrier = Barrier(2)

    def place_once(
        x_position: float,
    ) -> tuple[str, object | None]:
        start_barrier.wait()

        try:
            result = place_furniture(
                unit_of_work=SqlAlchemyUnitOfWork(
                    session_factory=session_factory,
                ),
                user_public_id=user_public_id,
                item_public_id=item_public_id,
                position_data=PositionData(
                    x=x_position,
                    y=20,
                    z=30,
                ),
            )
        except PlacementLimitExceededError:
            return "limit", None

        return "success", result

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(place_once, 10),
                executor.submit(place_once, 15),
            ]
            results = [future.result(timeout=10) for future in futures]

        with session_factory() as verification_session:
            placed_objects = verification_session.scalars(
                select(PlacedObject).where(
                    PlacedObject.user_id == user_id,
                    PlacedObject.item_id == item_id,
                )
            ).all()
            persisted_asset = verification_session.scalar(
                select(Asset).where(
                    Asset.user_id == user_id,
                    Asset.item_id == item_id,
                )
            )

            assert sorted(status for status, _ in results) == [
                "limit",
                "success",
            ]
            assert len(placed_objects) == 1
            assert persisted_asset is not None
            assert persisted_asset.quantity == 1
    finally:
        with session_factory() as cleanup_session:
            cleanup_session.execute(delete(PlacedObject).where(PlacedObject.user_id == user_id))
            cleanup_session.execute(delete(Asset).where(Asset.user_id == user_id))
            cleanup_session.execute(delete(User).where(User.id == user_id))
            cleanup_session.execute(delete(Item).where(Item.id == item_id))
            cleanup_session.commit()


def test_gacha_rolls_back_duplicate_mileage_when_completion_fails(
    db_session,
    monkeypatch,
) -> None:
    user = User(
        email=f"gacha-rollback-{uuid.uuid4()}@example.com",
        username=f"gacha-rollback-user-{uuid.uuid4()}",
        balance=1000,
        mileage=10,
    )
    cat = Cat(
        name=f"gacha-rollback-cat-{uuid.uuid4()}",
        persona="Rollback test cat",
        rarity="COMMON",
    )
    db_session.add_all([user, cat])
    db_session.flush()

    existing_asset = Asset(
        user_id=user.id,
        cat_id=cat.id,
        quantity=1,
    )
    db_session.add(existing_asset)
    db_session.flush()

    user_id = user.id
    asset_id = existing_asset.id
    request_id = uuid.uuid4()

    class FixedDuplicatePolicy:
        def calculate_balance_cost(
            self,
            *,
            draw_count: int,
        ) -> int:
            assert draw_count == 1
            return 200

        def draw(
            self,
            *,
            draw_count: int,
        ) -> list[GachaReward]:
            assert draw_count == 1
            return [
                GachaReward(
                    cat_public_id=cat.public_id,
                    duplicate_mileage=25,
                )
            ]

    original_complete = SqlAlchemyExecutionRepository.complete

    def fail_after_result_save(
        repository,
        execution,
        *,
        balance_cost: int,
        result_data: dict[str, object],
    ) -> None:
        original_complete(
            repository,
            execution,
            balance_cost=balance_cost,
            result_data=result_data,
        )
        repository._session.flush()
        raise RuntimeError("forced failure after execution result save")

    monkeypatch.setattr(
        SqlAlchemyExecutionRepository,
        "complete",
        fail_after_result_save,
    )

    session_factory = sessionmaker(
        bind=db_session.connection(),
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    with pytest.raises(
        RuntimeError,
        match="forced failure after execution result save",
    ):
        draw_cats(
            unit_of_work=SqlAlchemyUnitOfWork(
                session_factory=session_factory,
            ),
            policy=FixedDuplicatePolicy(),
            user_public_id=user.public_id,
            request_id=request_id,
            draw_count=1,
        )

    db_session.expire_all()

    persisted_user = db_session.get(User, user_id)
    persisted_asset = db_session.get(Asset, asset_id)
    execution = db_session.scalar(
        select(GachaExecution).where(GachaExecution.request_id == request_id)
    )

    assert persisted_user is not None
    assert persisted_user.balance == 1000
    assert persisted_user.mileage == 10
    assert persisted_asset is not None
    assert persisted_asset.quantity == 1
    assert execution is None
