import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request, Response
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.main import app
from app.models.auth_session import AuthSession
from app.modules.identity.router import _issue_session, current_session, development_session
from app.modules.identity.security import hash_token


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
    configured_origin = settings.cors_origin_list()[0]
    response = TestClient(app).options(
        "/api/v1/learning/recommendations",
        headers={
            "Origin": configured_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-CSRF-Token, X-Request-ID, X-User-Public-ID",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == configured_origin
    assert "X-Request-ID" in response.headers["access-control-allow-headers"]
    assert response.headers["X-Request-ID"]


def test_cors_preflight_allows_cat_memory_delete() -> None:
    response = TestClient(app).options(
        f"/api/v1/cats/{uuid.uuid4()}/memories",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "X-User-Public-ID",
        },
    )

    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_local_header_auth_resolves_public_user(monkeypatch) -> None:
    user = user_fixture()
    monkeypatch.setattr(settings, "app_env", "local")

    assert get_current_user(_request(), ExistingUserSession(user), user.public_id) is user


def test_temporary_header_auth_is_rejected_in_production(monkeypatch) -> None:
    user = user_fixture()
    monkeypatch.setattr(settings, "app_env", "production")

    with pytest.raises(HTTPException) as error:
        get_current_user(_request(), ExistingUserSession(user), user.public_id)

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


@pytest.mark.parametrize(
    ("method", "path"),
    [
        (
            "PUT",
            f"/api/v1/housing/surfaces/{uuid.uuid4()}",
        ),
        (
            "PATCH",
            (f"/api/v1/housing/placed-objects/{uuid.uuid4()}"),
        ),
    ],
)
def test_cors_preflight_allows_housing_changes(
    method: str,
    path: str,
) -> None:
    response = TestClient(app).options(
        path,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": ("X-User-Public-ID"),
        },
    )

    assert response.status_code == 200
    assert method in response.headers["access-control-allow-methods"]


def test_production_session_cookie_is_secure_and_http_only(monkeypatch) -> None:
    response = Response()
    db = ExistingUserSession(user_fixture())
    db.add = lambda value: setattr(db, "auth_session", value)
    monkeypatch.setattr(settings, "app_env", "production")

    _issue_session(db, response, SimpleNamespace(id=17))

    cookies = response.headers.getlist("set-cookie")
    session_cookie = next(value for value in cookies if value.startswith("__Host-nyang_session="))
    csrf_cookie = next(value for value in cookies if value.startswith("nyang_csrf="))
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert isinstance(db.auth_session, AuthSession)
    assert len(db.auth_session.token_hash) == 64


def test_cookie_auth_requires_matching_csrf_for_mutations(monkeypatch) -> None:
    user = user_fixture()
    auth_session = SimpleNamespace(
        user_id=4,
        csrf_token_hash=hash_token("valid-csrf"),
    )
    db = ExistingUserSession(auth_session)
    db.get = lambda _model, _user_id: user
    monkeypatch.setattr(settings, "app_env", "local")

    with pytest.raises(HTTPException) as error:
        get_current_user(
            _request("PATCH"),
            db,
            csrf_token="invalid-csrf",
            local_session="opaque-session",
        )
    assert error.value.status_code == 403

    resolved = get_current_user(
        _request("PATCH"),
        db,
        csrf_token="valid-csrf",
        local_session="opaque-session",
    )
    assert resolved is user


def _request(method: str = "GET") -> Request:
    return Request({"type": "http", "method": method, "headers": []})
