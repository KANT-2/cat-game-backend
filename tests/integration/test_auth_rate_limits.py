import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.main import app


def test_failed_logins_are_blocked_in_shared_database(engine, monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_login_attempt_limit", 3)
    _clear_limits(engine)
    client = TestClient(app)
    email = f"login-rate-{uuid.uuid4()}@example.com"
    registration = client.post(
        "/api/v1/session/register",
        json={"email": email, "username": "rate-test", "password": "correct-horse-2026"},
    )
    assert registration.status_code == 201

    assert _login(client, email, "wrong-password").status_code == 401
    assert _login(client, email, "wrong-password").status_code == 401
    blocked = _login(client, email, "wrong-password")
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "too-many-authentication-attempts"}
    assert int(blocked.headers["Retry-After"]) > 0
    assert _login(client, email, "correct-horse-2026").status_code == 429
    _clear_limits(engine)


def test_registration_requests_are_limited_by_hashed_client_bucket(engine, monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_registration_attempt_limit", 2)
    _clear_limits(engine)
    client = TestClient(app)

    for index in range(2):
        response = client.post(
            "/api/v1/session/register",
            json={
                "email": f"register-rate-{index}-{uuid.uuid4()}@example.com",
                "username": f"rate-test-{index}",
                "password": "correct-horse-2026",
            },
        )
        assert response.status_code == 201
    blocked = client.post(
        "/api/v1/session/register",
        json={
            "email": f"register-rate-blocked-{uuid.uuid4()}@example.com",
            "username": "rate-test-blocked",
            "password": "correct-horse-2026",
        },
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    _clear_limits(engine)


def _login(client: TestClient, email: str, password: str):
    return client.post("/api/v1/session/login", json={"email": email, "password": password})


def _clear_limits(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM auth_rate_limits"))
