"""Server-authoritative date and time helpers."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings


def game_today() -> date:
    """Return the current calendar date in the configured game timezone."""
    return datetime.now(ZoneInfo(settings.game_timezone)).date()


def game_day_bounds(day: date) -> tuple[datetime, datetime]:
    """Return one game-local calendar day's half-open UTC timestamp range."""
    timezone = ZoneInfo(settings.game_timezone)
    start = datetime.combine(day, time.min, tzinfo=timezone)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone)
    return start.astimezone(UTC), end.astimezone(UTC)
