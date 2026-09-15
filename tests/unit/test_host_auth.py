from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api import dependencies
from app.core.config import settings


class Response:
    status_code = 200
    is_redirect = False

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "id": 42,
            "display_name": "여름",
            "role": "student",
            "profile_image": "/media/profiles/summer.jpg",
        }


class Client:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    get = AsyncMock(return_value=Response())


class DB:
    def __init__(self):
        self.user = None

    def scalar(self, statement):
        return self.user

    def add(self, user):
        self.user = user

    def commit(self):
        pass

    def refresh(self, user):
        user.id = 1


def request(
    cookie: str | None = None,
    *,
    method: str = "GET",
    csrf_token: str | None = None,
):
    cookies = [] if cookie is None else [f"sessionid={cookie}"]
    if csrf_token is not None:
        cookies.append(f"nyang_csrf={csrf_token}")
    headers = [] if not cookies else [(b"cookie", "; ".join(cookies).encode())]
    if csrf_token is not None:
        headers.append((b"x-csrf-token", csrf_token.encode()))
    return Request({"type": "http", "method": method, "path": "/", "headers": headers})


@pytest.mark.asyncio
async def test_host_session_jit_provisions_and_updates_user(monkeypatch):
    monkeypatch.setattr(settings, "ax_auth_base_url", "http://host.test")
    monkeypatch.setattr(dependencies.httpx, "AsyncClient", Client)
    db = DB()
    first_request = request("secret")
    user = await dependencies.resolve_current_user(first_request, db, None)
    assert (user.homepage_user_id, user.username, user.role) == (42, "여름", "STUDENT")
    assert first_request.state.host_user.profile_image == "/media/profiles/summer.jpg"
    user.username = "old"
    updated = await dependencies.resolve_current_user(request("secret"), db, None)
    assert updated is user
    assert updated.username == "여름"


@pytest.mark.asyncio
async def test_host_session_cookie_is_required(monkeypatch):
    monkeypatch.setattr(settings, "ax_auth_base_url", "http://host.test")
    with pytest.raises(HTTPException) as exc:
        await dependencies.resolve_current_user(request(), DB(), None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_host_session_mutation_requires_bound_csrf_token(monkeypatch):
    monkeypatch.setattr(settings, "ax_auth_base_url", "http://host.test")
    monkeypatch.setattr(settings, "auth_rate_limit_secret", "test-auth-rate-limit-secret")
    monkeypatch.setattr(dependencies.httpx, "AsyncClient", Client)

    with pytest.raises(HTTPException) as exc:
        await dependencies.resolve_current_user(request("secret", method="POST"), DB(), None)
    assert exc.value.status_code == 403

    csrf_token = dependencies.host_csrf_token("secret")
    user = await dependencies.resolve_current_user(
        request("secret", method="POST", csrf_token=csrf_token),
        DB(),
        None,
    )
    assert user.homepage_user_id == 42
