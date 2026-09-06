"""Health probe for the durable grading worker loop."""

import time
from pathlib import Path

from app.core.config import settings

HEARTBEAT_PATH = Path("/tmp/cat-game-grading-worker.heartbeat")


def record_worker_heartbeat(path: Path = HEARTBEAT_PATH) -> None:
    """Record that the worker completed a queue database poll.

    The heartbeat lives on the container tmpfs, so an old process instance cannot
    make a restarted worker appear ready.
    """
    path.touch(exist_ok=True)


def is_worker_ready(path: Path = HEARTBEAT_PATH, now_epoch: float | None = None) -> bool:
    """Return whether the queue loop has reported recently enough.

    The allowed age includes two sandbox timeouts so a legitimate in-flight grade
    does not make the worker unhealthy.
    """
    try:
        heartbeat_epoch = path.stat().st_mtime
    except OSError:
        return False
    checked_at = time.time() if now_epoch is None else now_epoch
    age_seconds = checked_at - heartbeat_epoch
    max_age_seconds = max(
        30.0,
        settings.grading_timeout_seconds * 2 + settings.grading_poll_seconds * 4,
    )
    return 0 <= age_seconds <= max_age_seconds


def main() -> None:
    """Exit successfully only while the worker queue loop is responsive."""
    if not is_worker_ready():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
