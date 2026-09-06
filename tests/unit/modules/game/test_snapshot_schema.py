import uuid

from app.modules.game.schemas import GameCatRead, GameSnapshotRead


def test_snapshot_serializes_public_catalog_contract_without_internal_ids() -> None:
    cat_asset_public_id = uuid.uuid4()
    payload = GameSnapshotRead(
        catalog_version=1,
        state_version=1,
        balance=100,
        mileage=0,
        house_level=1,
        active_cat_key="fluffy",
        active_wallpaper_key=None,
        active_floor_key=None,
        attendance_last_claim_date="",
        attendance_streak=0,
        attendance_longest_streak=0,
        attendance_claimed_dates=[],
        daily_quest_date="2026-09-05",
        daily_completed_task_ids=[],
        daily_has_code_completion=False,
        claimed_daily_quest_ids=[],
        daily_bonus_claimed=False,
        settings={
            "bgm_enabled": True,
            "bgm_volume": 70,
            "effects_enabled": True,
            "effects_volume": 80,
            "reduced_motion": False,
        },
        cats=[
            {
                "public_id": uuid.uuid4(),
                "cat_asset_public_id": cat_asset_public_id,
                "catalog_key": "fluffy",
                "name": "포근이",
                "persona": "다정함",
                "rarity": "COMMON",
                "owned": True,
                "is_home": True,
                "memories": ["반복문을 연습했어요"],
            }
        ],
        items=[],
        placements=[],
    ).model_dump(mode="json")

    assert payload["active_cat_key"] == "fluffy"
    assert "id" not in payload
    assert "id" not in payload["cats"][0]
    assert "public_id" in payload["cats"][0]
    assert payload["cats"][0]["cat_asset_public_id"] == str(cat_asset_public_id)


def test_snapshot_uses_null_asset_public_id_for_unowned_catalog_cat() -> None:
    payload = GameCatRead(
        public_id=uuid.uuid4(),
        cat_asset_public_id=None,
        catalog_key="ink",
        name="먹구름",
        persona="조용하고 관찰력이 좋다.",
        rarity="RARE",
        owned=False,
        is_home=False,
        memories=[],
    ).model_dump(mode="json")

    assert payload["cat_asset_public_id"] is None
