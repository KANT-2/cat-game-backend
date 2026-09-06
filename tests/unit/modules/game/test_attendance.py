from datetime import date
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AlreadyClaimedError
from app.models.attendance import Attendance
from app.models.user import User
from app.modules.game.commands import claim_attendance


def test_claim_attendance_awards_third_day_bonus() -> None:
    user = User(id=1, balance=500, state_version=3)
    latest = Attendance(user_id=1, check_in_date=date(2026, 9, 4), streak_count=2)
    db = MagicMock()
    db.scalar.side_effect = [user, latest]

    result = claim_attendance(db, user, today=date(2026, 9, 5))

    assert result == {
        "claimed_date": "2026-09-05",
        "current_streak": 3,
        "daily_coins": 100,
        "streak_bonus": 150,
        "coins_awarded": 250,
    }
    assert user.balance == 750
    assert user.state_version == 4
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_claim_attendance_rejects_duplicate_day_without_reward() -> None:
    user = User(id=1, balance=500, state_version=3)
    latest = Attendance(user_id=1, check_in_date=date(2026, 9, 5), streak_count=3)
    db = MagicMock()
    db.scalar.side_effect = [user, latest]

    with pytest.raises(AlreadyClaimedError):
        claim_attendance(db, user, today=date(2026, 9, 5))

    assert user.balance == 500
    assert user.state_version == 3
    db.add.assert_not_called()
    db.commit.assert_not_called()
