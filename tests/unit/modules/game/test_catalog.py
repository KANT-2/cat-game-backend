from app.modules.game.catalog import CAT_DEFINITIONS, ITEM_DEFINITIONS, STARTER_ITEM_QUANTITIES


def test_catalog_keys_are_unique_and_prices_are_nonnegative() -> None:
    cat_keys = [definition.catalog_key for definition in CAT_DEFINITIONS]
    item_keys = [definition.catalog_key for definition in ITEM_DEFINITIONS]

    assert len(cat_keys) == len(set(cat_keys))
    assert len(item_keys) == len(set(item_keys))
    assert all(definition.price >= 0 for definition in ITEM_DEFINITIONS)


def test_starter_items_reference_placeable_catalog_entries() -> None:
    items = {definition.catalog_key: definition for definition in ITEM_DEFINITIONS}

    for catalog_key in STARTER_ITEM_QUANTITIES:
        definition = items[catalog_key]
        assert definition.category == "FURNITURE"
        assert definition.furniture_kind is not None
        assert definition.width is not None and definition.width > 0
        assert definition.height is not None and definition.height > 0


def test_cat_personas_match_the_four_public_characters() -> None:
    cats = {definition.catalog_key: definition for definition in CAT_DEFINITIONS}

    assert {key: definition.name for key, definition in cats.items()} == {
        "fluffy": "포근이",
        "ink": "먹구름",
        "siamese": "모카",
        "tabby": "호박이",
    }
    assert all(len(definition.persona) >= 30 for definition in cats.values())
