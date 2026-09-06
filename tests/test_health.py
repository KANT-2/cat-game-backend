import json
import logging

from fastapi.testclient import TestClient

from app.main import app, create_app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_readiness_checks_database() -> None:
    response = TestClient(app).get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_request_id_is_echoed_and_logged_without_request_data(caplog) -> None:
    caplog.set_level(logging.INFO, logger="uvicorn.error.cat_game.requests")
    response = TestClient(app).get(
        "/health?password=never-log-this",
        headers={"X-Request-ID": "browser-request-123"},
    )
    event = json.loads(caplog.records[-1].message)

    assert response.headers["X-Request-ID"] == "browser-request-123"
    assert event == {
        "event": "request_completed",
        "request_id": "browser-request-123",
        "method": "GET",
        "path": "/health",
        "status_code": 200,
        "duration_ms": event["duration_ms"],
    }
    assert "never-log-this" not in caplog.text


def test_invalid_request_id_is_replaced() -> None:
    response = TestClient(app).get("/health", headers={"X-Request-ID": "bad id with spaces"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "bad id with spaces"
    assert len(response.headers["X-Request-ID"]) == 36


def test_unhandled_error_returns_safe_reference_without_exception_detail(caplog) -> None:
    test_app = create_app()

    @test_app.get("/_test/failure")
    def fail_with_sensitive_message() -> None:
        raise RuntimeError("submitted-code-must-not-be-logged")

    caplog.set_level(logging.ERROR, logger="uvicorn.error.cat_game.requests")
    response = TestClient(test_app).get(
        "/_test/failure",
        headers={"X-Request-ID": "failed-request-123"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "internal-server-error",
        "request_id": "failed-request-123",
    }
    assert response.headers["X-Request-ID"] == "failed-request-123"
    assert "submitted-code-must-not-be-logged" not in caplog.text
