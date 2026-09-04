from typing import get_type_hints

from app.core.repository_contracts import (
    AssetRepository,
    CatMemoryRepository,
    CatRepository,
    ExecutionRepository,
    ItemRepository,
    PlacedObjectRepository,
    UserRepository,
)
from app.core.unit_of_work import UnitOfWork

EXPECTED_REPOSITORIES = {
    "users": UserRepository,
    "items": ItemRepository,
    "cats": CatRepository,
    "assets": AssetRepository,
    "executions": ExecutionRepository,
    "placed_objects": PlacedObjectRepository,
    "cat_memories": CatMemoryRepository,
}


def test_unit_of_work_exposes_all_repositories() -> None:
    assert get_type_hints(UnitOfWork) == EXPECTED_REPOSITORIES


def test_unit_of_work_owns_transaction_boundary() -> None:
    expected_methods = {
        "__enter__",
        "__exit__",
        "commit",
        "rollback",
    }

    assert expected_methods <= vars(UnitOfWork).keys()
