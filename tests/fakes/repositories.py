import uuid
from datetime import UTC, datetime

from app.core.repository_contracts import (
    ClaimStatus,
    ExecutionClaim,
)
from app.models.asset import Asset
from app.models.cat import Cat
from app.models.cat_memory import CatMemory
from app.models.gacha_execution import GachaExecution
from app.models.item import Item
from app.models.placed_object import PlacedObject
from app.models.user import User


class FakeExecutionRepository:
    def __init__(self) -> None:
        self.executions: dict[uuid.UUID, GachaExecution] = {}

    def claim(
        self,
        *,
        user_id: int,
        request_id: uuid.UUID,
        request_hash: str,
        request_payload: dict[str, object],
        operation_type: str,
    ) -> ExecutionClaim:
        existing = self.executions.get(request_id)

        if existing is not None:
            if existing.user_id != user_id or existing.request_hash != request_hash:
                return ExecutionClaim(
                    status=ClaimStatus.HASH_CONFLICT,
                    execution=existing,
                )

            status = (
                ClaimStatus.COMPLETED
                if existing.status == ClaimStatus.COMPLETED
                else ClaimStatus.ACQUIRED
            )
            return ExecutionClaim(status=status, execution=existing)

        execution = GachaExecution(
            id=len(self.executions) + 1,
            public_id=uuid.uuid4(),
            user_id=user_id,
            request_id=request_id,
            request_hash=request_hash,
            request_payload=dict(request_payload),
            operation_type=operation_type,
            status=ClaimStatus.ACQUIRED,
            draw_count=None,
            balance_cost=0,
            result_data=None,
            created_at=datetime.now(UTC),
            completed_at=None,
        )
        self.executions[request_id] = execution

        return ExecutionClaim(
            status=ClaimStatus.ACQUIRED,
            execution=execution,
        )

    def complete(
        self,
        execution: GachaExecution,
        *,
        balance_cost: int,
        result_data: dict[str, object],
    ) -> None:
        if balance_cost < 0:
            raise ValueError("balance_cost must be nonnegative")

        execution.balance_cost = balance_cost
        execution.result_data = dict(result_data)
        execution.status = ClaimStatus.COMPLETED
        execution.completed_at = datetime.now(UTC)


class FakeUserRepository:
    def __init__(self, users: list[User] | None = None) -> None:
        self.users = list(users or [])

    def get_by_public_id(self, public_id: uuid.UUID) -> User | None:
        return next(
            (user for user in self.users if user.public_id == public_id),
            None,
        )

    def get_for_update(self, user_id: int) -> User | None:
        return next(
            (user for user in self.users if user.id == user_id),
            None,
        )


class FakeItemRepository:
    def __init__(self, items: list[Item] | None = None) -> None:
        self.items = list(items or [])

    def get_by_public_id(self, public_id: uuid.UUID) -> Item | None:
        return next(
            (item for item in self.items if item.public_id == public_id),
            None,
        )

    def get_by_id(self, item_id: int) -> Item | None:
        return next(
            (item for item in self.items if item.id == item_id),
            None,
        )


class FakeCatRepository:
    def __init__(self, cats: list[Cat] | None = None) -> None:
        self.cats = list(cats or [])

    def get_by_public_id(self, public_id: uuid.UUID) -> Cat | None:
        return next(
            (cat for cat in self.cats if cat.public_id == public_id),
            None,
        )

    def get_by_id(self, cat_id: int) -> Cat | None:
        return next(
            (cat for cat in self.cats if cat.id == cat_id),
            None,
        )

    def list_all(self) -> list[Cat]:
        return sorted(self.cats, key=lambda cat: cat.id)


class FakeAssetRepository:
    def __init__(self, assets: list[Asset] | None = None) -> None:
        self.assets = list(assets or [])

    def get_by_public_id(
        self,
        public_id: uuid.UUID,
    ) -> Asset | None:
        return next(
            (asset for asset in self.assets if asset.public_id == public_id),
            None,
        )

    def get_cat_asset(
        self,
        user_id: int,
        cat_id: int,
    ) -> Asset | None:
        return next(
            (asset for asset in self.assets if asset.user_id == user_id and asset.cat_id == cat_id),
            None,
        )

    def list_cat_assets_by_user_id(
        self,
        user_id: int,
    ) -> list[Asset]:
        return sorted(
            (
                asset
                for asset in self.assets
                if asset.user_id == user_id and asset.cat_id is not None
            ),
            key=lambda asset: asset.id,
        )

    def get_item_asset_for_update(
        self,
        user_id: int,
        item_id: int,
    ) -> Asset | None:
        return next(
            (
                asset
                for asset in self.assets
                if asset.user_id == user_id and asset.item_id == item_id
            ),
            None,
        )

    def add_item_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity: int,
    ) -> Asset:
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        existing = self.get_item_asset_for_update(user_id, item_id)
        if existing is not None:
            existing.quantity += quantity
            return existing

        asset = Asset(
            id=len(self.assets) + 1,
            public_id=uuid.uuid4(),
            user_id=user_id,
            cat_id=None,
            item_id=item_id,
            quantity=quantity,
        )
        self.assets.append(asset)
        return asset

    def grant_cat(
        self,
        user_id: int,
        cat_id: int,
    ) -> Asset:
        existing = self.get_cat_asset(user_id, cat_id)
        if existing is not None:
            return existing

        asset = Asset(
            id=len(self.assets) + 1,
            public_id=uuid.uuid4(),
            user_id=user_id,
            cat_id=cat_id,
            item_id=None,
            quantity=1,
        )
        self.assets.append(asset)
        return asset


class FakePlacedObjectRepository:
    def __init__(
        self,
        placed_objects: list[PlacedObject] | None = None,
    ) -> None:
        self.placed_objects = list(placed_objects or [])

    def get_by_public_id_for_update(
        self,
        public_id: uuid.UUID,
    ) -> PlacedObject | None:
        return next(
            (
                placed_object
                for placed_object in self.placed_objects
                if placed_object.public_id == public_id
            ),
            None,
        )

    def count_for_update(
        self,
        user_id: int,
        item_id: int,
    ) -> int:
        return sum(
            placed.user_id == user_id and placed.item_id == item_id
            for placed in self.placed_objects
        )

    def add(
        self,
        user_id: int,
        item_id: int,
        position_data: dict[str, object],
    ) -> PlacedObject:
        placed = PlacedObject(
            id=len(self.placed_objects) + 1,
            public_id=uuid.uuid4(),
            user_id=user_id,
            item_id=item_id,
            position_data=dict(position_data),
        )
        self.placed_objects.append(placed)
        return placed

    def remove(
        self,
        placed_object: PlacedObject,
    ) -> None:
        self.placed_objects.remove(placed_object)


class FakeCatMemoryRepository:
    def __init__(
        self,
        memories: list[CatMemory] | None = None,
    ) -> None:
        self.memories = list(memories or [])

    def get_by_public_id_for_update(
        self,
        public_id: uuid.UUID,
    ) -> CatMemory | None:
        return next(
            (memory for memory in self.memories if memory.public_id == public_id),
            None,
        )

    def list_by_cat_asset_id(
        self,
        cat_asset_id: int,
    ) -> list[CatMemory]:
        memories = [memory for memory in self.memories if memory.cat_asset_id == cat_asset_id]
        return sorted(
            memories,
            key=lambda memory: (
                memory.created_at,
                memory.id,
            ),
        )

    def add(
        self,
        cat_asset_id: int,
        context_summary: str,
    ) -> CatMemory:
        memory = CatMemory(
            id=len(self.memories) + 1,
            public_id=uuid.uuid4(),
            cat_asset_id=cat_asset_id,
            context_summary=context_summary,
            created_at=datetime.now(UTC),
        )
        self.memories.append(memory)
        return memory

    def remove(
        self,
        memory: CatMemory,
    ) -> None:
        self.memories.remove(memory)

    def remove_all_by_cat_asset_id(
        self,
        cat_asset_id: int,
    ) -> None:
        self.memories[:] = [
            memory for memory in self.memories if memory.cat_asset_id != cat_asset_id
        ]
