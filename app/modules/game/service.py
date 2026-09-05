"""Read model for the server-authoritative game state."""

from collections import Counter
from datetime import UTC, datetime, time, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.attendance import Attendance
from app.models.cat import Cat
from app.models.daily_reward_claim import DailyRewardClaim
from app.models.item import Item
from app.models.placed_object import PlacedObject
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.models.user import User
from app.modules.game.bootstrap import bootstrap_starter_pack
from app.modules.game.catalog import ITEM_BY_KEY
from app.modules.game.schemas import (
    GameCatRead,
    GameItemRead,
    GamePlacementRead,
    GameSettingsRead,
    GameSnapshotRead,
)


def get_game_snapshot(db: Session, user: User) -> GameSnapshotRead:
    """Load the complete public game state after applying one-time player initialization.

    @param db: Request-scoped database session.
    @param user: Authenticated player resolved by the API dependency.
    @returns A consistent catalog and player state containing no internal database IDs.

    @remarks Starter initialization is committed before the snapshot is read.
    """
    if bootstrap_starter_pack(db, user):
        db.commit()
        db.refresh(user)

    cats = list(db.scalars(select(Cat).order_by(Cat.catalog_key)).all())
    items = list(db.scalars(select(Item).order_by(Item.catalog_key)).all())
    assets = list(db.scalars(select(Asset).where(Asset.user_id == user.id)).all())
    placements = list(
        db.scalars(
            select(PlacedObject).where(PlacedObject.user_id == user.id).order_by(PlacedObject.id)
        ).all()
    )
    attendances = list(
        db.scalars(
            select(Attendance)
            .where(Attendance.user_id == user.id)
            .order_by(Attendance.check_in_date)
        ).all()
    )
    today = datetime.now(UTC).date()
    day_start = datetime.combine(today, time.min, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    completed_rows = list(
        db.execute(
            select(Task.public_id, Task.type)
            .join(TaskAttempt, TaskAttempt.task_id == Task.id)
            .where(
                TaskAttempt.user_id == user.id,
                TaskAttempt.status == "COMPLETED",
                TaskAttempt.is_correct.is_(True),
                TaskAttempt.attempted_at >= day_start,
                TaskAttempt.attempted_at < day_end,
            )
            .distinct()
        ).all()
    )
    daily_claims = list(
        db.scalars(
            select(DailyRewardClaim).where(
                DailyRewardClaim.user_id == user.id,
                DailyRewardClaim.claim_date == today,
            )
        ).all()
    )

    cat_assets = {asset.cat_id: asset for asset in assets if asset.cat_id is not None}
    item_assets = {asset.item_id: asset for asset in assets if asset.item_id is not None}
    item_by_id = {item.id: item for item in items}
    placed_counts = Counter(placement.item_id for placement in placements)

    active_cat = next((cat for cat in cats if cat.id == user.active_cat_id), None)
    if active_cat is None:
        raise RuntimeError("player has no active catalog cat")

    return GameSnapshotRead(
        catalog_version=1,
        state_version=1,
        balance=user.balance,
        mileage=user.mileage,
        house_level=user.house_level,
        active_cat_key=active_cat.catalog_key,
        active_wallpaper_key=_item_key(item_by_id, user.wallpaper_item_id),
        active_floor_key=_item_key(item_by_id, user.floor_item_id),
        attendance_last_claim_date=(
            attendances[-1].check_in_date.isoformat() if attendances else ""
        ),
        attendance_streak=attendances[-1].streak_count if attendances else 0,
        attendance_longest_streak=max(
            (attendance.streak_count for attendance in attendances),
            default=0,
        ),
        attendance_claimed_dates=[attendance.check_in_date.isoformat() for attendance in attendances],
        daily_quest_date=today.isoformat(),
        daily_completed_task_ids=[str(row.public_id) for row in completed_rows],
        daily_has_code_completion=any(row.type == "CODE" for row in completed_rows),
        claimed_daily_quest_ids=[
            claim.reward_key for claim in daily_claims if claim.reward_key != "bonus"
        ],
        daily_bonus_claimed=any(claim.reward_key == "bonus" for claim in daily_claims),
        settings=_read_settings(user.game_settings),
        cats=[
            GameCatRead(
                public_id=cat.public_id,
                catalog_key=cat.catalog_key,
                name=cat.name,
                persona=cat.persona,
                rarity=cat.rarity,
                owned=cat.id in cat_assets,
                is_home=cat_assets[cat.id].is_home if cat.id in cat_assets else False,
            )
            for cat in cats
        ],
        items=[_read_item(item, item_assets.get(item.id), placed_counts[item.id]) for item in items],
        placements=[_read_placement(placement, item_by_id) for placement in placements],
    )


def _read_item(item: Item, asset: Asset | None, placed_count: int) -> GameItemRead:
    definition = ITEM_BY_KEY.get(item.catalog_key)
    owned_quantity = asset.quantity if asset is not None else 0
    return GameItemRead(
        public_id=item.public_id,
        catalog_key=item.catalog_key,
        category=item.category,
        name=item.name,
        price=item.price,
        furniture_kind=definition.furniture_kind if definition else None,
        width=definition.width if definition else None,
        height=definition.height if definition else None,
        owned_quantity=owned_quantity,
        available_quantity=max(0, owned_quantity - placed_count),
    )


def _read_placement(
    placement: PlacedObject,
    item_by_id: dict[int, Item],
) -> GamePlacementRead:
    item = item_by_id.get(placement.item_id)
    if item is None:
        raise RuntimeError("placement references a missing catalog item")
    position = placement.position_data
    return GamePlacementRead(
        public_id=placement.public_id,
        item_catalog_key=item.catalog_key,
        x=int(position["x"]),
        y=int(position["y"]),
        rotation=int(position["z"]),
    )


def _item_key(item_by_id: dict[int, Item], item_id: int | None) -> str | None:
    if item_id is None:
        return None
    item = item_by_id.get(item_id)
    return item.catalog_key if item is not None else None


def _read_settings(raw: dict[str, object]) -> GameSettingsRead:
    return GameSettingsRead(
        bgm_enabled=cast(bool, raw.get("bgmEnabled", True)),
        bgm_volume=cast(int, raw.get("bgmVolume", 70)),
        effects_enabled=cast(bool, raw.get("effectsEnabled", True)),
        effects_volume=cast(int, raw.get("effectsVolume", 80)),
        reduced_motion=cast(bool, raw.get("reducedMotion", False)),
    )
