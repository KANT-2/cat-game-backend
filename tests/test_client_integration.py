import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.main import app
from app.modules.identity.router import current_session, development_session


class ExistingUserSession:
    def __init__(self, user):
        self.user = user

    def scalar(self, _statement):
        return self.user

    def add(self, _value):
        raise AssertionError("the existing development user must be reused")


def user_fixture():
    return SimpleNamespace(
        public_id=uuid.uuid4(),
        email="player@local.nyang",
        username="{ 냥 } 플레이어",
        role="STUDENT",
        balance=1_100_000,
        mileage=0,
        house_level=1,
        created_at=datetime.now(UTC),
    )


def test_cors_preflight_accepts_configured_pwa_origin() -> None:
    response = TestClient(app).options(
        "/api/v1/learning/recommendations",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-User-Public-ID",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_local_header_auth_resolves_public_user(monkeypatch) -> None:
    user = user_fixture()
    monkeypatch.setattr(settings, "app_env", "local")

    assert get_current_user(ExistingUserSession(user), user.public_id) is user


def test_temporary_header_auth_is_rejected_in_production(monkeypatch) -> None:
    user = user_fixture()
    monkeypatch.setattr(settings, "app_env", "production")

    with pytest.raises(HTTPException) as error:
        get_current_user(ExistingUserSession(user), user.public_id)

    assert error.value.status_code == 401


def test_development_session_reuses_public_user(monkeypatch) -> None:
    user = user_fixture()
    monkeypatch.setattr(settings, "app_env", "local")

    response = development_session(ExistingUserSession(user))

    assert response.public_id == user.public_id
    assert response.email == "player@local.nyang"


def test_current_session_exposes_only_public_user_fields() -> None:
    user = user_fixture()

    response = current_session(user)

    assert response.public_id == user.public_id
    assert "id" not in response.model_dump()


def test_development_session_is_hidden_in_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")

    with pytest.raises(HTTPException) as error:
        development_session(ExistingUserSession(user_fixture()))

    assert error.value.status_code == 404
