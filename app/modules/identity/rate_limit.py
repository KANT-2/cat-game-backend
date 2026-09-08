import hashlib
import hmac
import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth_rate_limit import AuthRateLimit


def auth_bucket_hash(scope: str, value: str) -> str:
    """Create a keyed, non-reversible bucket identifier without storing email or IP text."""
    normalized = f"{scope}:{value.strip().lower()}".encode()
    return hmac.new(
        settings.auth_rate_limit_secret.encode(),
        normalized,
        hashlib.sha256,
    ).hexdigest()


def lock_rate_buckets(
    db: Session,
    bucket_hashes: list[str],
    *,
    now: datetime | None = None,
) -> list[AuthRateLimit]:
    """Create missing buckets and lock all matching rows for one authentication decision."""
    current_time = now or datetime.now(UTC)
    unique_hashes = list(dict.fromkeys(bucket_hashes))
    if db.get_bind().dialect.name == "postgresql":
        statement = postgresql_insert(AuthRateLimit).values(
            [
                {
                    "bucket_hash": bucket_hash,
                    "attempts": 0,
                    "window_started_at": current_time,
                }
                for bucket_hash in unique_hashes
            ]
        )
        db.execute(statement.on_conflict_do_nothing(index_elements=["bucket_hash"]))
    else:
        existing = set(
            db.scalars(
                select(AuthRateLimit.bucket_hash).where(
                    AuthRateLimit.bucket_hash.in_(unique_hashes)
                )
            )
        )
        for bucket_hash in unique_hashes:
            if bucket_hash not in existing:
                db.add(
                    AuthRateLimit(
                        bucket_hash=bucket_hash,
                        attempts=0,
                        window_started_at=current_time,
                    )
                )
        db.flush()
    buckets = list(
        db.scalars(
            select(AuthRateLimit)
            .where(AuthRateLimit.bucket_hash.in_(unique_hashes))
            .with_for_update()
        )
    )
    if len(buckets) != len(unique_hashes):
        raise RuntimeError("authentication rate limit bucket creation failed")
    for bucket in buckets:
        _refresh_window(bucket, current_time)
    return buckets


def blocked_retry_after(
    buckets: list[AuthRateLimit],
    *,
    attempt_limit: int,
    now: datetime | None = None,
) -> int | None:
    """Return the longest active block and start a block when a window is exhausted."""
    current_time = now or datetime.now(UTC)
    retry_after = 0
    for bucket in buckets:
        _refresh_window(bucket, current_time)
        blocked_until = _aware(bucket.blocked_until)
        if blocked_until and blocked_until > current_time:
            retry_after = max(retry_after, math.ceil((blocked_until - current_time).total_seconds()))
            continue
        if bucket.attempts >= attempt_limit:
            bucket.blocked_until = current_time + timedelta(seconds=settings.auth_rate_block_seconds)
            retry_after = max(retry_after, settings.auth_rate_block_seconds)
    return retry_after or None


def record_failed_attempts(
    buckets: list[AuthRateLimit],
    *,
    attempt_limit: int,
    now: datetime | None = None,
) -> int | None:
    """Increment failure counters and return a block duration when the threshold is reached."""
    current_time = now or datetime.now(UTC)
    blocked = False
    for bucket in buckets:
        bucket.attempts += 1
        bucket.updated_at = current_time
        if bucket.attempts >= attempt_limit:
            bucket.blocked_until = current_time + timedelta(seconds=settings.auth_rate_block_seconds)
            blocked = True
    return settings.auth_rate_block_seconds if blocked else None


def record_request_attempt(buckets: list[AuthRateLimit], *, now: datetime | None = None) -> None:
    """Count a registration request after the caller has verified that its bucket is allowed."""
    current_time = now or datetime.now(UTC)
    for bucket in buckets:
        bucket.attempts += 1
        bucket.updated_at = current_time


def reset_rate_bucket(bucket: AuthRateLimit, *, now: datetime | None = None) -> None:
    """Clear an account failure bucket after successful credential verification."""
    current_time = now or datetime.now(UTC)
    bucket.attempts = 0
    bucket.blocked_until = None
    bucket.window_started_at = current_time
    bucket.updated_at = current_time


def _refresh_window(bucket: AuthRateLimit, now: datetime) -> None:
    window_started_at = _aware(bucket.window_started_at)
    blocked_until = _aware(bucket.blocked_until)
    if blocked_until is not None and blocked_until <= now:
        bucket.attempts = 0
        bucket.blocked_until = None
        bucket.window_started_at = now
        bucket.updated_at = now
        return
    if window_started_at + timedelta(seconds=settings.auth_rate_window_seconds) > now:
        return
    bucket.attempts = 0
    bucket.blocked_until = None
    bucket.window_started_at = now
    bucket.updated_at = now


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)
