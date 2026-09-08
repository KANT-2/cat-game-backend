"""Versioned static game catalog shared by seeding and authoritative rules."""

from dataclasses import dataclass

CATALOG_VERSION = 2


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
    consumable_effect: str | None = None


CAT_DEFINITIONS = (
    CatDefinition(
        "fluffy",
        "포근이",
        "느긋하고 다정하다. 짧고 포근한 말투로 서두르지 않아도 괜찮다고 안심시킨다.",
        "COMMON",
    ),
    CatDefinition(
        "ink",
        "먹구름",
        "조용하고 관찰력이 좋다. 말수는 적지만 작은 변화를 짚으며 생각할 여백을 준다.",
        "RARE",
    ),
    CatDefinition(
        "siamese",
        "모카",
        "영리하고 수다스럽다. 호기심 어린 질문과 작은 예시로 생각을 이어 가게 한다.",
        "COMMON",
    ),
    CatDefinition(
        "tabby",
        "호박이",
        "활동적이고 낙천적이다. 장난스러운 감탄과 행동 제안으로 망설임을 가볍게 만든다.",
        "RARE",
    ),
)

ITEM_DEFINITIONS = (
    ItemDefinition("furniture.sofa", "FURNITURE", "버섯 숲 벤치", 4_800, "sofa", 3, 1),
    ItemDefinition("furniture.table", "FURNITURE", "낮은 원목 탁자", 3_200, "desk", 2, 1),
    ItemDefinition("furniture.catTower", "FURNITURE", "잎사귀 스크래처", 4_200, "catTree", 2, 1),
    ItemDefinition("furniture.bed", "FURNITURE", "초록 발바닥 쿠션", 5_600, "bed", 3, 2),
    ItemDefinition("furniture.desk", "FURNITURE", "통나무 숨숨집", 3_900, "desk", 2, 1),
    ItemDefinition("furniture.premiumTower", "FURNITURE", "거목 캣타워", 90, "catTree", 2, 1),
    ItemDefinition("decor.plant", "FURNITURE", "분홍 들꽃 덤불", 1_700, "plant", 1, 1),
    ItemDefinition("decor.reed-clump", "FURNITURE", "햇살 갈대숲", 900, "plant", 1, 1),
    ItemDefinition("decor.rock-angular", "FURNITURE", "뾰족 이끼바위", 1_100, "plant", 1, 1),
    ItemDefinition("decor.rock-round", "FURNITURE", "둥근 이끼바위", 1_200, "plant", 1, 1),
    ItemDefinition("decor.fallen-log", "FURNITURE", "이끼 낀 쓰러진 통나무", 1_800, "rug", 3, 1),
    ItemDefinition("decor.cardboard-box", "FURNITURE", "골목의 열린 상자", 700, "plant", 1, 1),
    ItemDefinition("decor.trash-bag", "FURNITURE", "묶어 둔 골목 봉투", 600, "plant", 1, 1),
    ItemDefinition("decor.sealed-box", "FURNITURE", "테이프로 봉한 상자", 800, "plant", 1, 1),
    ItemDefinition("decor.plastic-crate", "FURNITURE", "낡은 플라스틱 바구니", 750, "plant", 1, 1),
    ItemDefinition("decor.alley-food-bowl", "FURNITURE", "골목의 분홍 밥그릇", 550, "plant", 1, 1),
    ItemDefinition("decor.alley-water-bowl", "FURNITURE", "골목의 파란 물그릇", 550, "plant", 1, 1),
    ItemDefinition("decor.crushed-can", "FURNITURE", "찌그러진 빨간 캔", 180, "plant", 1, 1),
    ItemDefinition("decor.old-brick", "FURNITURE", "이끼 묻은 벽돌", 220, "plant", 1, 1),
    ItemDefinition("decor.paper-ball", "FURNITURE", "구겨진 종이공", 160, "plant", 1, 1),
    ItemDefinition("decor.plastic-bottle", "FURNITURE", "납작한 물병", 180, "plant", 1, 1),
    ItemDefinition("decor.newspaper-stack", "FURNITURE", "묶어 둔 신문 더미", 350, "plant", 1, 1),
    ItemDefinition("decor.litter-scoop", "FURNITURE", "민트색 모래삽", 400, "plant", 1, 1),
    ItemDefinition("decor.yarn-ball", "FURNITURE", "분홍 털실공", 450, "plant", 1, 1),
    ItemDefinition("decor.teaser-set", "FURNITURE", "깃털 낚싯대 세트", 650, "plant", 1, 1),
    ItemDefinition("decor.fur-pile", "FURNITURE", "복슬복슬 털뭉치", 300, "plant", 1, 1),
    ItemDefinition("decor.room-water-bowl", "FURNITURE", "민트 발바닥 물그릇", 600, "plant", 1, 1),
    ItemDefinition("decor.room-food-bowl", "FURNITURE", "민트 발바닥 밥그릇", 600, "plant", 1, 1),
    ItemDefinition("furniture.forest.rug", "FURNITURE", "나뭇잎 원형 러그", 2_100, "rug", 3, 1),
    ItemDefinition(
        "furniture.forest.cat-tower", "FURNITURE", "거목 놀이터 캣타워", 4_900, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.forest.hideout", "FURNITURE", "통나무 숲 숨숨집", 3_600, "hideout", 2, 1
    ),
    ItemDefinition(
        "furniture.forest.scratcher", "FURNITURE", "잎사귀 스크래처", 2_800, "scratcher", 2, 1
    ),
    ItemDefinition(
        "furniture.forest.litter-box", "FURNITURE", "이끼숲 화장실", 3_400, "litterBox", 2, 1
    ),
    ItemDefinition("furniture.forest.rug-2", "FURNITURE", "고사리 잎방석", 2_300, "rug", 3, 1),
    ItemDefinition(
        "furniture.forest.cat-tower-2", "FURNITURE", "돌샘 숲 캣타워", 5_300, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.forest.hideout-2", "FURNITURE", "그루터기 동굴 숨숨집", 3_900, "hideout", 2, 1
    ),
    ItemDefinition(
        "furniture.forest.scratcher-2",
        "FURNITURE",
        "덩굴 통나무 스크래처",
        3_000,
        "scratcher",
        2,
        1,
    ),
    ItemDefinition(
        "furniture.forest.litter-box-2", "FURNITURE", "돌담 모래 화장실", 3_700, "litterBox", 2, 1
    ),
    ItemDefinition(
        "furniture.forest.bench-2", "FURNITURE", "꽃그늘 버섯 벤치", 5_000, "sofa", 3, 1
    ),
    ItemDefinition(
        "furniture.forest.cat-tower-3", "FURNITURE", "가지 쉼터 캣타워", 4_800, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.forest.hideout-3", "FURNITURE", "이끼 동굴 숨숨집", 4_100, "hideout", 2, 1
    ),
    ItemDefinition("furniture.alley.rug", "FURNITURE", "골목빛 패브릭 러그", 1_900, "rug", 3, 1),
    ItemDefinition(
        "furniture.alley.cat-tower", "FURNITURE", "상자 요새 캣타워", 4_600, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.alley.hideout", "FURNITURE", "골목 상자 숨숨집", 3_200, "hideout", 2, 1
    ),
    ItemDefinition(
        "furniture.alley.scratcher", "FURNITURE", "골목 기둥 스크래처", 2_500, "scratcher", 2, 1
    ),
    ItemDefinition(
        "furniture.alley.litter-box", "FURNITURE", "나무 상자 화장실", 3_000, "litterBox", 2, 1
    ),
    ItemDefinition("furniture.alley.rug-2", "FURNITURE", "신문지 포근 매트", 1_700, "rug", 3, 1),
    ItemDefinition(
        "furniture.alley.cat-tower-2", "FURNITURE", "폐목재 골목 캣타워", 4_200, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.alley.hideout-2", "FURNITURE", "천막 나무상자 숨숨집", 2_900, "hideout", 2, 1
    ),
    ItemDefinition(
        "furniture.alley.scratcher-2", "FURNITURE", "골목 경사 스크래처", 2_200, "scratcher", 2, 1
    ),
    ItemDefinition(
        "furniture.alley.scratcher-3", "FURNITURE", "세로 골판지 스크래처", 2_600, "scratcher", 2, 1
    ),
    ItemDefinition(
        "furniture.alley.litter-box-2", "FURNITURE", "골목 나무틀 화장실", 2_800, "litterBox", 2, 1
    ),
    ItemDefinition(
        "furniture.alley.litter-box-3",
        "FURNITURE",
        "골목 철제 모래 화장실",
        3_200,
        "litterBox",
        2,
        1,
    ),
    ItemDefinition("furniture.room.rug", "FURNITURE", "포근한 방 러그", 2_400, "rug", 3, 1),
    ItemDefinition(
        "furniture.room.cat-tower", "FURNITURE", "거실 원목 캣타워", 5_200, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.room.hideout", "FURNITURE", "원목 상자 숨숨집", 3_800, "hideout", 2, 1
    ),
    ItemDefinition(
        "furniture.room.scratcher", "FURNITURE", "거실 기둥 스크래처", 2_900, "scratcher", 2, 1
    ),
    ItemDefinition(
        "furniture.room.litter-box", "FURNITURE", "원목 고양이 화장실", 3_500, "litterBox", 2, 1
    ),
    ItemDefinition("furniture.room.rug-2", "FURNITURE", "잎사귀 테두리 러그", 2_600, "rug", 3, 1),
    ItemDefinition(
        "furniture.room.cat-tower-2", "FURNITURE", "클래식 원목 캣타워", 5_000, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.room.cat-tower-3", "FURNITURE", "화분 해먹 캣타워", 5_600, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.room.hideout-2", "FURNITURE", "패브릭 원목 숨숨집", 4_100, "hideout", 2, 1
    ),
    ItemDefinition(
        "furniture.room.scratcher-2", "FURNITURE", "거실 경사 스크래처", 3_100, "scratcher", 2, 1
    ),
    ItemDefinition(
        "furniture.room.litter-box-2", "FURNITURE", "화이트 원목 화장실", 3_800, "litterBox", 2, 1
    ),
    ItemDefinition("furniture.desk-theme.rug", "FURNITURE", "서재 포인트 러그", 2_300, "rug", 3, 1),
    ItemDefinition(
        "furniture.desk-theme.cat-tower", "FURNITURE", "책상 옆 캣타워", 4_800, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.desk-theme.hideout", "FURNITURE", "서재 원목 숨숨집", 3_700, "hideout", 2, 1
    ),
    ItemDefinition(
        "furniture.desk-theme.scratcher", "FURNITURE", "클립보드 스크래처", 2_700, "scratcher", 2, 1
    ),
    ItemDefinition(
        "furniture.desk-theme.litter-box",
        "FURNITURE",
        "서재 수납형 화장실",
        3_300,
        "litterBox",
        2,
        1,
    ),
    ItemDefinition(
        "furniture.desk-theme.rug-2", "FURNITURE", "메모지 발바닥 러그", 2_500, "rug", 3, 1
    ),
    ItemDefinition(
        "furniture.desk-theme.cat-tower-2", "FURNITURE", "책더미 캣타워", 5_100, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.desk-theme.hideout-2", "FURNITURE", "택배 상자 숨숨집", 3_900, "hideout", 2, 1
    ),
    ItemDefinition(
        "furniture.desk-theme.scratcher-2",
        "FURNITURE",
        "연필 경사 스크래처",
        2_900,
        "scratcher",
        2,
        1,
    ),
    ItemDefinition(
        "furniture.desk-theme.litter-box-2",
        "FURNITURE",
        "서재 화이트 화장실",
        3_500,
        "litterBox",
        2,
        1,
    ),
    ItemDefinition("furniture.ocean.rug", "FURNITURE", "조개빛 해변 러그", 2_500, "rug", 3, 1),
    ItemDefinition(
        "furniture.ocean.cat-tower", "FURNITURE", "모래성 캣타워", 5_400, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.ocean.hideout", "FURNITURE", "파도 동굴 숨숨집", 4_000, "hideout", 2, 1
    ),
    ItemDefinition(
        "furniture.ocean.scratcher", "FURNITURE", "해변 곡선 스크래처", 3_000, "scratcher", 2, 1
    ),
    ItemDefinition(
        "furniture.ocean.litter-box", "FURNITURE", "조개 정원 화장실", 3_700, "litterBox", 2, 1
    ),
    ItemDefinition("furniture.ocean.rug-2", "FURNITURE", "밧줄 해변 러그", 2_700, "rug", 3, 1),
    ItemDefinition(
        "furniture.ocean.cat-tower-2", "FURNITURE", "조개 모래성 캣타워", 5_200, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.ocean.cat-tower-3", "FURNITURE", "등대 해변 캣타워", 5_700, "catTree", 2, 1
    ),
    ItemDefinition(
        "furniture.ocean.hideout-2", "FURNITURE", "파란 해변 오두막", 4_200, "hideout", 2, 1
    ),
    ItemDefinition(
        "furniture.ocean.scratcher-2", "FURNITURE", "파도 경사 스크래처", 3_200, "scratcher", 2, 1
    ),
    ItemDefinition(
        "furniture.ocean.litter-box-2", "FURNITURE", "민트 조개 화장실", 3_900, "litterBox", 2, 1
    ),
    ItemDefinition(
        "consumable.salmon-cubes", "CONSUMABLE", "연어 큐브 간식", 180, consumable_effect="happy"
    ),
    ItemDefinition(
        "consumable.chicken-strips", "CONSUMABLE", "닭가슴살 스틱", 150, consumable_effect="relaxed"
    ),
    ItemDefinition(
        "consumable.catnip-biscuits",
        "CONSUMABLE",
        "캣닢 잎사귀 비스킷",
        220,
        consumable_effect="playful",
    ),
    ItemDefinition(
        "consumable.tuna-soup", "CONSUMABLE", "참치 크림 수프", 200, consumable_effect="curious"
    ),
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
