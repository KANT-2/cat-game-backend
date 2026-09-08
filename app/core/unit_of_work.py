from types import TracebackType
from typing import Protocol, Self

from app.core.repository_contracts import (
    AssetRepository,
    CatMemoryRepository,
    CatRepository,
    ExecutionRepository,
    ItemRepository,
    PlacedObjectRepository,
    UserRepository,
)


class UnitOfWork(Protocol):
    users: UserRepository
    items: ItemRepository
    cats: CatRepository
    assets: AssetRepository
    executions: ExecutionRepository
    placed_objects: PlacedObjectRepository
    cat_memories: CatMemoryRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
