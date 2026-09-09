import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.exceptions import AIProviderUnavailableError
from app.integrations.ai.cat_chat import RuleBasedCatChatProvider
from app.main import app
from app.modules.cats import service as cat_service
from app.modules.cats.router import get_cat_chat_provider, get_cat_unit_of_work


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


def test_cat_chat_dependency_uses_safe_fallback_when_key_is_missing(monkeypatch) -> None:
    get_cat_chat_provider.cache_clear()
    monkeypatch.setattr(settings, "gemini_api_key", None)

    try:
        provider = get_cat_chat_provider()
    finally:
        get_cat_chat_provider.cache_clear()

    assert isinstance(provider, RuleBasedCatChatProvider)


def test_cat_chat_rejects_invalid_body_before_calling_service(monkeypatch) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    provider = MagicMock()
    chat = MagicMock()
    monkeypatch.setattr(cat_service, "chat_with_cat", chat)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work
    app.dependency_overrides[get_cat_chat_provider] = lambda: provider

    try:
        response = TestClient(app).post(
            f"/api/v1/cats/{uuid.uuid4()}/chat",
            json={"message": ""},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    chat.assert_not_called()


def test_cat_chat_maps_provider_failure_to_service_unavailable(monkeypatch) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    provider = MagicMock()
    monkeypatch.setattr(
        cat_service,
        "chat_with_cat",
        MagicMock(side_effect=AIProviderUnavailableError("provider failed")),
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work
    app.dependency_overrides[get_cat_chat_provider] = lambda: provider

    try:
        response = TestClient(app).post(
            f"/api/v1/cats/{uuid.uuid4()}/chat",
            json={"message": "안녕"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "cat-chat-unavailable"
