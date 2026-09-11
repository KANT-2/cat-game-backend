"""Small authoritative commands not covered by economy or housing services."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AlreadyClaimedError,
    ResourceNotFoundError,
    RewardNotReadyError,
)
from app.core.time import game_day_bounds, game_today
from app.models.asset import Asset
from app.models.attendance import Attendance
from app.models.attendance_task import AttendanceTask
from app.models.cat import Cat
from app.models.cat_memory import CatMemory
from app.models.daily_reward_claim import DailyRewardClaim
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.models.user import User
from app.models.user_learning_tier import UserLearningTier
from app.models.user_proficiency import UserProficiency

ATTENDANCE_DAILY_COINS = 100
ATTENDANCE_BONUSES = {3: 150, 7: 500}
DAILY_REWARDS = {"solve-one": 50, "solve-three": 100, "finish-code": 150, "bonus": 310}


def select_active_cat(db: Session, user: User, catalog_key: str) -> None:
    """Select an owned cat and make it visible at home in one transaction."""
    cat = db.scalar(select(Cat).where(Cat.catalog_key == catalog_key))
    if cat is None:
        raise ResourceNotFoundError("cat not found")
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")
    asset = db.scalar(
        select(Asset)
        .where(Asset.user_id == user.id, Asset.cat_id == cat.id)
        .with_for_update()
    )
    if asset is None:
        raise ResourceNotFoundError("cat asset not found")
    asset.is_home = True
    locked_user.active_cat_id = cat.id
    locked_user.advance_state_version()
    db.commit()


def set_cat_home(db: Session, user: User, catalog_key: str, *, visible: bool) -> None:
    """Change an owned cat's home visibility and keep the active selection valid."""
    cat = db.scalar(select(Cat).where(Cat.catalog_key == catalog_key))
    if cat is None:
        raise ResourceNotFoundError("cat not found")
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")
    asset = db.scalar(
        select(Asset)
        .where(Asset.user_id == user.id, Asset.cat_id == cat.id)
        .with_for_update()
    )
    if asset is None:
        raise ResourceNotFoundError("cat asset not found")
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
    locked_user.advance_state_version()
    db.commit()


def update_game_settings(db: Session, user: User, patch: dict[str, object]) -> None:
    """Merge validated settings keys into the server-owned JSON document."""
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")
    locked_user.game_settings = {**locked_user.game_settings, **patch}
    locked_user.advance_state_version()
    db.commit()


def claim_attendance(db: Session, user: User, *, today: date | None = None) -> dict[str, object]:
    """Claim the configured game calendar day's attendance reward exactly once.

    @param db: Request-scoped database session and transaction.
    @param user: Authenticated player receiving the reward.
    @param today: Injectable game-local date for deterministic tests.
    @returns Claimed date, current streak, bonus, and total awarded coins.
    @throws AlreadyClaimedError: Attendance already exists for the selected date.
    """
    claim_date = today or game_today()
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
    locked_user.advance_state_version()
    db.commit()
    return {
        "claimed_date": claim_date.isoformat(),
        "current_streak": streak,
        "daily_coins": ATTENDANCE_DAILY_COINS,
        "streak_bonus": bonus,
        "coins_awarded": awarded,
    }


def claim_daily_reward(
    db: Session,
    user: User,
    reward_key: str,
    *,
    today: date | None = None,
) -> dict[str, object]:
    """Validate today's completed attempts and grant one daily reward atomically."""
    if reward_key not in DAILY_REWARDS:
        raise ResourceNotFoundError("daily reward not found")
    claim_date = today or game_today()
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")
    existing = db.scalar(
        select(DailyRewardClaim.id).where(
            DailyRewardClaim.user_id == user.id,
            DailyRewardClaim.claim_date == claim_date,
            DailyRewardClaim.reward_key == reward_key,
        )
    )
    if existing is not None:
        raise AlreadyClaimedError("daily reward already claimed")

    if reward_key == "bonus":
        claimed_keys = set(
            db.scalars(
                select(DailyRewardClaim.reward_key).where(
                    DailyRewardClaim.user_id == user.id,
                    DailyRewardClaim.claim_date == claim_date,
                    DailyRewardClaim.reward_key != "bonus",
                )
            ).all()
        )
        if claimed_keys != {"solve-one", "solve-three", "finish-code"}:
            raise RewardNotReadyError("daily bonus is not ready")
    else:
        completed_count, has_code = _daily_completion_progress(
            db,
            user.id,
            claim_date,
            getattr(locked_user, "learning_reset_at", None),
        )
        ready = (
            (reward_key == "solve-one" and completed_count >= 1)
            or (reward_key == "solve-three" and completed_count >= 3)
            or (reward_key == "finish-code" and has_code)
        )
        if not ready:
            raise RewardNotReadyError("daily reward is not ready")

    awarded = DAILY_REWARDS[reward_key]
    db.add(
        DailyRewardClaim(
            user_id=user.id,
            claim_date=claim_date,
            reward_key=reward_key,
            coins_awarded=awarded,
        )
    )
    locked_user.balance += awarded
    locked_user.advance_state_version()
    db.commit()
    return {"reward_key": reward_key, "coins_awarded": awarded}


def _daily_completion_progress(
    db: Session,
    user_id: int,
    claim_date: date,
    learning_reset_at: datetime | None = None,
) -> tuple[int, bool]:
    day_start, day_end = game_day_bounds(claim_date)
    if learning_reset_at is not None and learning_reset_at > day_start:
        day_start = learning_reset_at
    rows = db.execute(
        select(TaskAttempt.task_id, Task.type)
        .join(Task, Task.id == TaskAttempt.task_id)
        .where(
            TaskAttempt.user_id == user_id,
            TaskAttempt.status == "COMPLETED",
            TaskAttempt.is_correct.is_(True),
            TaskAttempt.attempted_at >= day_start,
            TaskAttempt.attempted_at < day_end,
        )
        .distinct()
    ).all()
    return len(rows), any(row.type == "CODE" for row in rows)


def reset_learning_progress(db: Session, user: User) -> dict[str, object]:
    """Remove one user's learning history without refunding already granted rewards."""
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")

    reset_at = datetime.now(UTC)
    locked_user.learning_reset_at = reset_at
    proficiency_result = db.execute(
        delete(UserProficiency).where(UserProficiency.user_id == user.id)
    )
    db.execute(delete(UserLearningTier).where(UserLearningTier.user_id == user.id))
    attendance_ids = select(Attendance.id).where(Attendance.user_id == user.id)
    db.execute(
        update(AttendanceTask)
        .where(AttendanceTask.attendance_id.in_(attendance_ids))
        .values(is_completed=False)
    )
    locked_user.advance_state_version()
    db.commit()
    return {
        "reset_at": reset_at.isoformat(),
        "removed_proficiencies": proficiency_result.rowcount,
    }


def clear_cat_memories(db: Session, user: User) -> dict[str, object]:
    """Delete memories belonging to the authenticated user's cat assets only."""
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")
    cat_asset_ids = select(Asset.id).where(Asset.user_id == user.id, Asset.cat_id.is_not(None))
    result = db.execute(delete(CatMemory).where(CatMemory.cat_asset_id.in_(cat_asset_ids)))
    locked_user.advance_state_version()
    db.commit()
    return {"removed": result.rowcount}
