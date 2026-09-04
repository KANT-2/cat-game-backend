from app.core.repository_contracts import (
    AssetRepository,
    CatMemoryRepository,
    CatRepository,
    ExecutionRepository,
    ItemRepository,
    PlacedObjectRepository,
    UserRepository,
)

EXPECTED_METHODS = {
    ExecutionRepository: {"claim", "complete"},
    UserRepository: {"get_by_public_id", "get_for_update"},
    ItemRepository: {"get_by_public_id", "get_by_id"},
    CatRepository: {
    "get_by_public_id",
    "get_by_id",
    },
    AssetRepository: {
    "get_by_public_id",
    "get_cat_asset",
    "get_item_asset_for_update",
    "add_item_quantity",
    "grant_cat",
    },
    PlacedObjectRepository: {
        "get_by_public_id_for_update",
        "count_for_update",
        "add",
        "remove",
    },
    CatMemoryRepository: {
    "get_by_public_id_for_update",
    "list_by_cat_asset_id",
    "add",
    "remove",
    "remove_all_by_cat_asset_id",
    },
}


def test_repository_contracts_expose_only_expected_methods() -> None:
    for repository, expected_methods in EXPECTED_METHODS.items():
        actual_methods = {
            name
            for name, value in vars(repository).items()
            if callable(value) and not name.startswith("_")
        }

        assert actual_methods == expected_methods


def test_repository_contracts_do_not_own_transactions() -> None:
    for repository in EXPECTED_METHODS:
        assert "commit" not in vars(repository)
        assert "rollback" not in vars(repository)


def test_locking_methods_are_named_for_update() -> None:
    locking_methods = {
        UserRepository: {"get_for_update"},
        AssetRepository: {"get_item_asset_for_update"},
        PlacedObjectRepository: {
            "get_by_public_id_for_update",
            "count_for_update",
        },
        CatMemoryRepository: {
            "get_by_public_id_for_update",
        },
    }

    for repository, expected_methods in locking_methods.items():
        actual_methods = {
            name
            for name in vars(repository)
            if name.endswith("for_update")
        }

        assert actual_methods == expected_methods
