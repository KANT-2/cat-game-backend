"""Durable PostgreSQL-backed grading worker process."""

import json
import signal
import threading

from app.core.config import settings
from app.modules.grading.service import claim_next_attempt, grade_claimed_attempt


def run() -> None:
    """Poll and grade leased attempts until the process receives a termination signal."""
    settings.validate_production_secrets()
    stopping = threading.Event()

    def request_stop(_signum, _frame) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    _event("grading_worker_started")
    while not stopping.is_set():
        try:
            lease = claim_next_attempt()
            if lease is None:
                stopping.wait(settings.grading_poll_seconds)
                continue
            completed = grade_claimed_attempt(lease)
            _event(
                "grading_attempt_completed" if completed else "grading_attempt_deferred",
                attempt_public_id=str(lease.public_id),
            )
        except Exception:  # noqa: BLE001 - the polling boundary must survive database outages
            _event("grading_worker_poll_failed")
            stopping.wait(settings.grading_poll_seconds)
    _event("grading_worker_stopped")


def _event(name: str, **fields: str) -> None:
    payload = {"event": name, **fields}
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    run()
