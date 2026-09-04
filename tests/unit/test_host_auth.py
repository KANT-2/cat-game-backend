from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api import dependencies
from app.core.config import settings


class Response:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"id": 42, "display_name": "여름", "role": "student"}


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


def request(cookie: str | None = None):
    headers = [] if cookie is None else [(b"cookie", f"sessionid={cookie}".encode())]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


@pytest.mark.asyncio
async def test_host_session_jit_provisions_and_updates_user(monkeypatch):
    monkeypatch.setattr(settings, "ax_auth_base_url", "http://host.test")
    monkeypatch.setattr(dependencies.httpx, "AsyncClient", Client)
    db = DB()
    user = await dependencies.get_current_user(request("secret"), db)
    assert (user.homepage_user_id, user.username, user.role) == (42, "여름", "STUDENT")
    user.username = "old"
    updated = await dependencies.get_current_user(request("secret"), db)
    assert updated is user
    assert updated.username == "여름"


@pytest.mark.asyncio
async def test_host_session_cookie_is_required(monkeypatch):
    monkeypatch.setattr(settings, "ax_auth_base_url", "http://host.test")
    with pytest.raises(HTTPException) as exc:
        await dependencies.get_current_user(request(), DB())
    assert exc.value.status_code == 401
