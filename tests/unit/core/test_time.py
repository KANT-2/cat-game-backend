from datetime import UTC, date, datetime

from app.core.config import settings
from app.core.time import game_day_bounds


def test_game_day_bounds_converts_seoul_midnight_to_utc(monkeypatch):
    monkeypatch.setattr(settings, "game_timezone", "Asia/Seoul")

    start, end = game_day_bounds(date(2026, 9, 8))

    assert start == datetime(2026, 9, 7, 15, 0, tzinfo=UTC)
    assert end == datetime(2026, 9, 8, 15, 0, tzinfo=UTC)
