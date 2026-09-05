"""Small authoritative commands not covered by economy or housing services."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyClaimedError, ResourceNotFoundError
from app.models.asset import Asset
from app.models.attendance import Attendance
from app.models.cat import Cat
from app.models.user import User

ATTENDANCE_DAILY_COINS = 100
ATTENDANCE_BONUSES = {3: 150, 7: 500}


def select_active_cat(db: Session, user: User, catalog_key: str) -> None:
    """Select an owned cat and make it visible at home in one transaction."""
    cat = db.scalar(select(Cat).where(Cat.catalog_key == catalog_key))
    if cat is None:
        raise ResourceNotFoundError("cat not found")
    asset = db.scalar(
        select(Asset)
        .where(Asset.user_id == user.id, Asset.cat_id == cat.id)
        .with_for_update()
    )
    if asset is None:
        raise ResourceNotFoundError("cat asset not found")
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")
    asset.is_home = True
    locked_user.active_cat_id = cat.id
    db.commit()


def set_cat_home(db: Session, user: User, catalog_key: str, *, visible: bool) -> None:
    """Change an owned cat's home visibility and keep the active selection valid."""
    cat = db.scalar(select(Cat).where(Cat.catalog_key == catalog_key))
    if cat is None:
        raise ResourceNotFoundError("cat not found")
    asset = db.scalar(
        select(Asset)
        .where(Asset.user_id == user.id, Asset.cat_id == cat.id)
        .with_for_update()
    )
    if asset is None:
        raise ResourceNotFoundError("cat asset not found")
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")
    asset.is_home = visible
    if not visible and locked_user.active_cat_id == cat.id:
        replacement = db.scalar(
            select(Asset)
            .where(
                Asset.user_id == user.id,
                Asset.cat_id.is_not(None),
                Asset.is_home.is_(True),
                Asset.id != asset.id,
            )
            .order_by(Asset.id)
            .limit(1)
        )
        if replacement is not None:
            locked_user.active_cat_id = replacement.cat_id
    db.commit()


def update_game_settings(db: Session, user: User, patch: dict[str, object]) -> None:
    """Merge validated settings keys into the server-owned JSON document."""
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")
    locked_user.game_settings = {**locked_user.game_settings, **patch}
    db.commit()


def claim_attendance(db: Session, user: User, *, today: date | None = None) -> dict[str, object]:
    """Claim the UTC calendar day's attendance reward exactly once.

    @param db: Request-scoped database session and transaction.
    @param user: Authenticated player receiving the reward.
    @param today: Injectable UTC date for deterministic tests.
    @returns Claimed date, current streak, bonus, and total awarded coins.
    @throws AlreadyClaimedError: Attendance already exists for the selected date.
    """
    claim_date = today or datetime.now(UTC).date()
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")
    latest = db.scalar(
        select(Attendance)
        .where(Attendance.user_id == user.id)
        .order_by(Attendance.check_in_date.desc())
        .limit(1)
        .with_for_update()
    )
    if latest is not None and latest.check_in_date == claim_date:
        raise AlreadyClaimedError("attendance already claimed")
    yesterday = claim_date - timedelta(days=1)
    streak = latest.streak_count + 1 if latest and latest.check_in_date == yesterday else 1
    cycle_day = ((streak - 1) % 7) + 1
    bonus = ATTENDANCE_BONUSES.get(cycle_day, 0)
    awarded = ATTENDANCE_DAILY_COINS + bonus
    db.add(
        Attendance(
            user_id=locked_user.id,
            check_in_date=claim_date,
            streak_count=streak,
            daily_reward_claimed_at=datetime.now(UTC),
        )
    )
    locked_user.balance += awarded
    db.commit()
    return {
        "claimed_date": claim_date.isoformat(),
        "current_streak": streak,
        "daily_coins": ATTENDANCE_DAILY_COINS,
        "streak_bonus": bonus,
        "coins_awarded": awarded,
    }
