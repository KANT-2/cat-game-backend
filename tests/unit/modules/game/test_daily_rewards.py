from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AlreadyClaimedError, RewardNotReadyError
from app.models.daily_reward_claim import DailyRewardClaim
from app.modules.game.commands import claim_daily_reward


def test_claim_daily_reward_awards_completed_code_quest() -> None:
    user = SimpleNamespace(id=1, balance=500)
    db = MagicMock()
    db.scalar.side_effect = [user, None]
    db.execute.return_value.all.return_value = [SimpleNamespace(type="CODE")]

    result = claim_daily_reward(db, user, "finish-code", today=date(2026, 9, 5))

    assert result == {"reward_key": "finish-code", "coins_awarded": 150}
    assert user.balance == 650
    claim = db.add.call_args.args[0]
    assert isinstance(claim, DailyRewardClaim)
    assert claim.claim_date == date(2026, 9, 5)
    assert claim.reward_key == "finish-code"
    db.commit.assert_called_once()


def test_claim_daily_reward_rejects_incomplete_quest_without_reward() -> None:
    user = SimpleNamespace(id=1, balance=500)
    db = MagicMock()
    db.scalar.side_effect = [user, None]
    db.execute.return_value.all.return_value = [
        SimpleNamespace(type="MULTIPLE_CHOICE"),
        SimpleNamespace(type="CODE"),
    ]

    with pytest.raises(RewardNotReadyError):
        claim_daily_reward(db, user, "solve-three", today=date(2026, 9, 5))

    assert user.balance == 500
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_claim_daily_reward_rejects_duplicate_before_rechecking_progress() -> None:
    user = SimpleNamespace(id=1, balance=500)
    db = MagicMock()
    db.scalar.side_effect = [user, 42]

    with pytest.raises(AlreadyClaimedError):
        claim_daily_reward(db, user, "solve-one", today=date(2026, 9, 5))

    assert user.balance == 500
    db.execute.assert_not_called()
    db.add.assert_not_called()


def test_claim_daily_bonus_requires_all_three_quest_claims() -> None:
    user = SimpleNamespace(id=1, balance=500)
    db = MagicMock()
    db.scalar.side_effect = [user, None]
    db.scalars.return_value.all.return_value = ["solve-one", "solve-three"]

    with pytest.raises(RewardNotReadyError):
        claim_daily_reward(db, user, "bonus", today=date(2026, 9, 5))

    assert user.balance == 500
    db.add.assert_not_called()
