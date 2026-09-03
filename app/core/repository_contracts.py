from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.cat import Cat
    from app.models.cat_memory import CatMemory
    from app.models.gacha_execution import GachaExecution
    from app.models.item import Item
    from app.models.placed_object import PlacedObject
    from app.models.user import User


class ClaimStatus(StrEnum):
    ACQUIRED = "ACQUIRED"
    COMPLETED = "COMPLETED"
    HASH_CONFLICT = "HASH_CONFLICT"


@dataclass(frozen=True, slots=True)
class ExecutionClaim:
    status: ClaimStatus
    execution: GachaExecution


class ExecutionRepository(Protocol):
    def claim(
        self,
        *,
        user_id: int,
        request_id: UUID,
        request_hash: str,
        request_payload: dict[str, object],
        operation_type: str,
    ) -> ExecutionClaim: ...

    def complete(
        self,
        execution: GachaExecution,
        *,
        balance_cost: int,
        result_data: dict[str, object],
    ) -> None: ...


class UserRepository(Protocol):
    def get_by_public_id(self, public_id: UUID) -> User | None: ...

    def get_for_update(self, user_id: int) -> User | None: ...


class ItemRepository(Protocol):
    def get_by_public_id(self, public_id: UUID) -> Item | None: ...

    def get_by_id(self, item_id: int) -> Item | None: ...

class CatRepository(Protocol):
    def get_by_public_id(self, public_id: UUID) -> Cat | None: ...


class AssetRepository(Protocol):
    def get_cat_asset(
        self,
        user_id: int,
        cat_id: int,
    ) -> Asset | None: ...

    def get_item_asset_for_update(
        self,
        user_id: int,
        item_id: int,
    ) -> Asset | None: ...

    def add_item_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity: int,
    ) -> Asset: ...

    def grant_cat(
        self,
        user_id: int,
        cat_id: int,
    ) -> Asset: ...


class PlacedObjectRepository(Protocol):
    def get_by_public_id_for_update(
        self,
        public_id: UUID,
    ) -> PlacedObject | None: ...

    def count_for_update(
        self,
        user_id: int,
        item_id: int,
    ) -> int: ...

    def add(
        self,
        user_id: int,
        item_id: int,
        position_data: dict[str, object],
    ) -> PlacedObject: ...

    def remove(
        self,
        placed_object: PlacedObject,
    ) -> None: ...


class CatMemoryRepository(Protocol):
    def list_by_cat_asset_id(
        self,
        cat_asset_id: int,
    ) -> list[CatMemory]: ...

    def add(
        self,
        cat_asset_id: int,
        context_summary: str,
    ) -> CatMemory: ...
