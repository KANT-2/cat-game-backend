"""Structured request logging without sensitive payloads."""

import json
import logging

request_logger = logging.getLogger("uvicorn.error.cat_game.requests")


def log_request(
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    failed: bool = False,
) -> None:
    """Write one machine-readable request event without headers, query values, or body data."""
    event = {
        "event": "request_failed" if failed else "request_completed",
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }
    message = json.dumps(event, ensure_ascii=True, separators=(",", ":"))
    if failed:
        request_logger.error(message)
    else:
        request_logger.info(message)
