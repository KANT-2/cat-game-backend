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
    ItemDefinition("wallpaper.cream", "WALLPAPER", "숲길 공터", 2_100),
    ItemDefinition("wallpaper.cloud", "WALLPAPER", "햇살 숲 공터", 2_400),
    ItemDefinition("wallpaper.forest", "WALLPAPER", "폭포 숲", 2_800),
    ItemDefinition("wallpaper.flower", "WALLPAPER", "담쟁이 돌마당", 2_600),
    ItemDefinition("wallpaper.night", "WALLPAPER", "황혼의 서재", 70),
    ItemDefinition("wallpaper.cat", "WALLPAPER", "포근한 나무방", 3_000),
    ItemDefinition("wallpaper.modernAlley", "WALLPAPER", "푸른 하늘 골목", 2_900),
    ItemDefinition("wallpaper.villageAlley", "WALLPAPER", "오래된 동네 마당", 3_100),
    ItemDefinition("wallpaper.sunnyStudio", "WALLPAPER", "햇살 가득 스튜디오", 3_200),
    ItemDefinition("wallpaper.livingRoom", "WALLPAPER", "초록빛 거실", 3_400),
    ItemDefinition("wallpaper.cityOffice", "WALLPAPER", "도시 전망 작업실", 3_600),
    ItemDefinition("wallpaper.botanicalDesk", "WALLPAPER", "식물 연구 책상", 2_700),
    ItemDefinition("wallpaper.musicDesk", "WALLPAPER", "음악 감상 책상", 3_000),
    ItemDefinition("wallpaper.sandyCove", "WALLPAPER", "조개빛 모래 해변", 3_300),
    ItemDefinition("wallpaper.seasidePromenade", "WALLPAPER", "바닷바람 산책로", 3_500),
    ItemDefinition("wallpaper.workingHarbor", "WALLPAPER", "활기찬 항구", 3_800),
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
