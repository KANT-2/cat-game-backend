import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.exceptions import AIProviderUnavailableError
from app.integrations.ai.contracts import AIMessage
from app.main import app
from app.modules.cats import service as cat_service
from app.modules.cats.router import (
    get_cat_ai_client,
    get_cat_unit_of_work,
)


def test_cat_chat_route_is_registered() -> None:
    path = "/api/v1/cats/{cat_asset_public_id}/chat"

    assert path in app.openapi()["paths"]
    assert "post" in app.openapi()["paths"][path]


def test_cat_chat_requires_authentication() -> None:
    cat_asset_public_id = uuid.uuid4()

    response = TestClient(app).post(
        f"/api/v1/cats/{cat_asset_public_id}/chat",
        json={"message": "안녕"},
    )

    assert response.status_code == 401


def test_cat_ai_dependency_returns_503_when_key_is_missing(monkeypatch) -> None:
    get_cat_ai_client.cache_clear()
    monkeypatch.setattr(settings, "gemini_api_key", None)

    try:
        with pytest.raises(HTTPException) as exc_info:
            get_cat_ai_client()
    finally:
        get_cat_ai_client.cache_clear()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "AI service is not configured"


def test_cat_chat_returns_reply_memory_and_public_ids(monkeypatch) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    cat_asset_public_id = uuid.uuid4()
    memory_public_id = uuid.uuid4()
    unit_of_work = MagicMock()
    ai_client = MagicMock()
    chat = MagicMock(
        return_value={
            "cat_asset_public_id": cat_asset_public_id,
            "reply": "같이 반복문을 연습하자!",
            "memory": {
                "public_id": memory_public_id,
                "cat_asset_public_id": cat_asset_public_id,
                "context_summary": "사용자는 반복문을 공부하고 있다.",
                "created_at": datetime(2026, 9, 5, tzinfo=UTC),
            },
            "input_tokens": 40,
            "output_tokens": 12,
        }
    )
    monkeypatch.setattr(cat_service, "chat_with_cat", chat)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work
    app.dependency_overrides[get_cat_ai_client] = lambda: ai_client

    try:
        response = TestClient(app).post(
            f"/api/v1/cats/{cat_asset_public_id}/chat",
            json={
                "message": " 반복문을 알려줘 ",
                "recent_messages": [{"role": "assistant", "text": " 무엇을 공부할까? "}],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    chat.assert_called_once_with(
        unit_of_work=unit_of_work,
        ai_client=ai_client,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset_public_id,
        message="반복문을 알려줘",
        recent_messages=[AIMessage(role="assistant", text="무엇을 공부할까?")],
        max_output_tokens=512,
        max_memory_count=20,
    )

    body = response.json()
    assert body["cat_asset_public_id"] == str(cat_asset_public_id)
    assert body["memory"]["public_id"] == str(memory_public_id)
    assert body["input_tokens"] == 40
    assert body["output_tokens"] == 12
    assert "id" not in body
    assert "cat_asset_id" not in body["memory"]


def test_cat_chat_converts_provider_failure_to_503(monkeypatch) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    cat_asset_public_id = uuid.uuid4()
    unit_of_work = MagicMock()
    ai_client = MagicMock()
    monkeypatch.setattr(
        cat_service,
        "chat_with_cat",
        MagicMock(side_effect=AIProviderUnavailableError("quota exhausted")),
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work
    app.dependency_overrides[get_cat_ai_client] = lambda: ai_client

    try:
        response = TestClient(app).post(
            f"/api/v1/cats/{cat_asset_public_id}/chat",
            json={"message": "안녕"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "AI service is temporarily unavailable"}


def test_cat_chat_rejects_invalid_body_before_calling_service(monkeypatch) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    ai_client = MagicMock()
    chat = MagicMock()
    monkeypatch.setattr(cat_service, "chat_with_cat", chat)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work
    app.dependency_overrides[get_cat_ai_client] = lambda: ai_client

    try:
        response = TestClient(app).post(
            f"/api/v1/cats/{uuid.uuid4()}/chat",
            json={"message": "   "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    chat.assert_not_called()
