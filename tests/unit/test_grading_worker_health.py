import os
from pathlib import Path

from app.modules.grading.health import is_worker_ready, record_worker_heartbeat


def test_worker_is_not_ready_before_first_successful_poll(tmp_path: Path) -> None:
    assert is_worker_ready(tmp_path / "missing", now_epoch=100.0) is False


def test_worker_is_ready_after_recent_successful_poll(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat"
    record_worker_heartbeat(heartbeat)
    os.utime(heartbeat, (100.0, 100.0))

    assert is_worker_ready(heartbeat, now_epoch=110.0) is True


def test_worker_is_unhealthy_when_polling_heartbeat_is_stale(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat"
    record_worker_heartbeat(heartbeat)
    os.utime(heartbeat, (100.0, 100.0))

    assert is_worker_ready(heartbeat, now_epoch=10_000.0) is False


def test_future_heartbeat_does_not_mask_clock_or_file_corruption(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat"
    record_worker_heartbeat(heartbeat)
    os.utime(heartbeat, (200.0, 200.0))

    assert is_worker_ready(heartbeat, now_epoch=100.0) is False
