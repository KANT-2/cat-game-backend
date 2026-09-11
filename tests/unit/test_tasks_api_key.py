import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.api.dependencies import verify_tasks_api_key
from app.core.config import settings
from app.main import app


def test_tasks_api_key_accepts_matching_team_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tasks_api_key", SecretStr("team-secret"))

    assert verify_tasks_api_key("team-secret") is None


@pytest.mark.parametrize("provided", [None, "wrong-key"])
def test_tasks_api_key_rejects_missing_or_wrong_key(monkeypatch, provided) -> None:
    monkeypatch.setattr(settings, "tasks_api_key", SecretStr("team-secret"))

    with pytest.raises(HTTPException) as raised:
        verify_tasks_api_key(provided)

    assert raised.value.status_code == 401


def test_tasks_api_key_fails_closed_when_server_key_is_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tasks_api_key", None)

    with pytest.raises(HTTPException) as raised:
        verify_tasks_api_key("any-key")

    assert raised.value.status_code == 503


def test_every_task_management_operation_uses_team_key_without_member_login() -> None:
    paths = app.openapi()["paths"]
    operations = [
        paths["/api/v1/tasks"]["post"],
        paths["/api/v1/tasks/{task_public_id}"]["patch"],
        paths["/api/v1/tasks/{task_public_id}"]["delete"],
    ]

    for operation in operations:
        headers = {
            parameter["name"]
            for parameter in operation["parameters"]
            if parameter["in"] == "header"
        }
        assert "X-API-Key" in headers
        assert "X-User-Public-ID" not in headers
