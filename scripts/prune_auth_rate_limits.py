"""Delete expired authentication throttle buckets without exposing their identifiers."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth_rate_limit import AuthRateLimit


def main() -> None:
    retention_seconds = max(settings.auth_rate_window_seconds, settings.auth_rate_block_seconds) * 4
    cutoff = datetime.now(UTC) - timedelta(seconds=retention_seconds)
    with SessionLocal.begin() as db:
        result = db.execute(delete(AuthRateLimit).where(AuthRateLimit.updated_at < cutoff))
    print({"removed": result.rowcount, "cutoff": cutoff.isoformat()})


if __name__ == "__main__":
    main()
