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


def test_background_catalog_contains_all_selectable_places() -> None:
    backgrounds = [definition for definition in ITEM_DEFINITIONS if definition.category == "WALLPAPER"]

    assert len(backgrounds) == 16
    assert {definition.name for definition in backgrounds} == {
        "숲길 공터",
        "햇살 숲 공터",
        "폭포 숲",
        "담쟁이 돌마당",
        "황혼의 서재",
        "포근한 나무방",
        "푸른 하늘 골목",
        "오래된 동네 마당",
        "햇살 가득 스튜디오",
        "초록빛 거실",
        "도시 전망 작업실",
        "식물 연구 책상",
        "음악 감상 책상",
        "조개빛 모래 해변",
        "바닷바람 산책로",
        "활기찬 항구",
    }
