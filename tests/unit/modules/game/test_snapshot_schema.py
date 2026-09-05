import uuid

from app.modules.game.schemas import GameSnapshotRead


def test_snapshot_serializes_public_catalog_contract_without_internal_ids() -> None:
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
                "catalog_key": "fluffy",
                "name": "복실이",
                "persona": "다정함",
                "rarity": "COMMON",
                "owned": True,
                "is_home": True,
            }
        ],
        items=[],
        placements=[],
    ).model_dump(mode="json")

    assert payload["active_cat_key"] == "fluffy"
    assert "id" not in payload
    assert "id" not in payload["cats"][0]
    assert "public_id" in payload["cats"][0]
