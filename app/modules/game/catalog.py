"""Versioned static game catalog shared by seeding and authoritative rules."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatDefinition:
    catalog_key: str
    name: str
    persona: str
    rarity: str


@dataclass(frozen=True, slots=True)
class ItemDefinition:
    catalog_key: str
    category: str
    name: str
    price: int
    furniture_kind: str | None = None
    width: int | None = None
    height: int | None = None


CAT_DEFINITIONS = (
    CatDefinition("fluffy", "복실이", "느긋하고 다정한 첫 친구", "COMMON"),
    CatDefinition("ink", "먹구름", "호기심 많은 검은 고양이", "RARE"),
    CatDefinition("siamese", "샴이", "영리하고 수다스러운 친구", "COMMON"),
    CatDefinition("tabby", "고등어", "활동적이고 장난기 많은 친구", "RARE"),
)

ITEM_DEFINITIONS = (
    ItemDefinition("furniture.sofa", "FURNITURE", "버섯 숲 벤치", 4_800, "sofa", 3, 1),
    ItemDefinition("furniture.table", "FURNITURE", "낮은 원목 탁자", 3_200, "desk", 2, 1),
    ItemDefinition("furniture.catTower", "FURNITURE", "잎사귀 스크래처", 4_200, "catTree", 2, 1),
    ItemDefinition("furniture.bed", "FURNITURE", "초록 발바닥 쿠션", 5_600, "bed", 3, 2),
    ItemDefinition("furniture.desk", "FURNITURE", "통나무 숨숨집", 3_900, "desk", 2, 1),
    ItemDefinition("furniture.premiumTower", "FURNITURE", "거목 캣타워", 90, "catTree", 2, 1),
    ItemDefinition("decor.plant", "FURNITURE", "분홍 들꽃 덤불", 1_700, "plant", 1, 1),
    ItemDefinition("wallpaper.cream", "WALLPAPER", "크림빛 하늘", 2_100),
    ItemDefinition("wallpaper.cloud", "WALLPAPER", "구름빛 하늘", 2_400),
    ItemDefinition("wallpaper.forest", "WALLPAPER", "깊은 숲빛", 2_800),
    ItemDefinition("wallpaper.flower", "WALLPAPER", "꽃잎빛 하늘", 2_600),
    ItemDefinition("wallpaper.night", "WALLPAPER", "별이 뜬 밤", 70),
    ItemDefinition("wallpaper.cat", "WALLPAPER", "고양이 무늬", 3_000),
    ItemDefinition("floor.oak", "FLOOR", "참나무 길", 2_300),
    ItemDefinition("floor.check", "FLOOR", "체크 돗자리", 2_600),
    ItemDefinition("floor.stone", "FLOOR", "돌바닥 길", 2_800),
    ItemDefinition("floor.cream", "FLOOR", "크림빛 길", 2_100),
    ItemDefinition("floor.star", "FLOOR", "별빛 길", 65),
    ItemDefinition("floor.walnut", "FLOOR", "호두나무 길", 3_100),
)

CAT_BY_KEY = {definition.catalog_key: definition for definition in CAT_DEFINITIONS}
ITEM_BY_KEY = {definition.catalog_key: definition for definition in ITEM_DEFINITIONS}

STARTER_PACK_VERSION = 1
STARTER_CAT_KEYS = ("fluffy", "siamese")
STARTER_HOME_CAT_KEYS = ("fluffy",)
STARTER_ACTIVE_CAT_KEY = "fluffy"
STARTER_ITEM_QUANTITIES = {
    "furniture.table": 1,
    "furniture.sofa": 1,
    "decor.plant": 2,
    "furniture.catTower": 1,
    "furniture.bed": 1,
}
STARTER_PLACEMENTS = (
    ("furniture.table", 1, 1, 0),
    ("furniture.sofa", 5, 1, 0),
    ("decor.plant", 8, 2, 0),
    ("furniture.catTower", 0, 5, 0),
    ("furniture.bed", 6, 5, 0),
)

ROOM_GRID_WIDTH = 10
ROOM_GRID_HEIGHT = 8
