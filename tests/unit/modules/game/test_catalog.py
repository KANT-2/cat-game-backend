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
    backgrounds = [
        definition for definition in ITEM_DEFINITIONS if definition.category == "WALLPAPER"
    ]

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


def test_catalog_contains_complete_theme_furniture_and_positive_care_items() -> None:
    themed_furniture = [
        definition
        for definition in ITEM_DEFINITIONS
        if definition.category == "FURNITURE" and definition.catalog_key.count(".") >= 2
    ]
    consumables = [
        definition for definition in ITEM_DEFINITIONS if definition.category == "CONSUMABLE"
    ]

    assert len(themed_furniture) == 57
    assert len(consumables) == 4
    assert {definition.consumable_effect for definition in consumables} == {
        "happy",
        "playful",
        "relaxed",
        "curious",
    }


def test_catalog_contains_multiple_placeable_decorations() -> None:
    decorations = [
        definition for definition in ITEM_DEFINITIONS if definition.catalog_key.startswith("decor.")
    ]

    assert len(decorations) == 22
    assert {definition.name for definition in decorations} == {
        "분홍 들꽃 덤불",
        "햇살 갈대숲",
        "뾰족 이끼바위",
        "둥근 이끼바위",
        "이끼 낀 쓰러진 통나무",
        "골목의 열린 상자",
        "묶어 둔 골목 봉투",
        "테이프로 봉한 상자",
        "낡은 플라스틱 바구니",
        "골목의 분홍 밥그릇",
        "골목의 파란 물그릇",
        "찌그러진 빨간 캔",
        "이끼 묻은 벽돌",
        "구겨진 종이공",
        "납작한 물병",
        "묶어 둔 신문 더미",
        "민트색 모래삽",
        "분홍 털실공",
        "깃털 낚싯대 세트",
        "복슬복슬 털뭉치",
        "민트 발바닥 물그릇",
        "민트 발바닥 밥그릇",
    }
    assert all(definition.category == "FURNITURE" for definition in decorations)


def test_cat_personas_match_the_four_public_characters() -> None:
    cats = {definition.catalog_key: definition for definition in CAT_DEFINITIONS}

    assert {key: definition.name for key, definition in cats.items()} == {
        "fluffy": "포근이",
        "ink": "먹구름",
        "siamese": "모카",
        "tabby": "호박이",
    }
    assert all(len(definition.persona) >= 30 for definition in cats.values())
