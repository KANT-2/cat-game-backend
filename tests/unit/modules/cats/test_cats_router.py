import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.exceptions import (
    InvalidMemorySummaryError,
    ResourceNotFoundError,
)
from app.main import app
from app.modules.cats import service as cat_service
from app.modules.cats.router import get_cat_unit_of_work


def test_cat_conversation_context_route_is_registered() -> None:
    path = "/api/v1/cats/{cat_asset_public_id}/conversation-context"

    assert path in app.openapi()["paths"]
    assert "get" in app.openapi()["paths"][path]


def test_cat_conversation_context_requires_authentication() -> None:
    cat_asset_public_id = uuid.uuid4()

    response = TestClient(app).get(f"/api/v1/cats/{cat_asset_public_id}/conversation-context")

    assert response.status_code == 401


def test_get_cat_conversation_context_returns_public_response(
    monkeypatch,
) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    cat_asset_public_id = uuid.uuid4()
    cat_public_id = uuid.uuid4()
    memory_public_id = uuid.uuid4()

    get_context = MagicMock(
        return_value={
            "cat_asset_public_id": cat_asset_public_id,
            "cat_public_id": cat_public_id,
            "name": "나비",
            "persona": "차분하고 다정한 고양이",
            "memories": [
                {
                    "public_id": memory_public_id,
                    "cat_asset_public_id": cat_asset_public_id,
                    "context_summary": "사용자는 반복문을 공부했다.",
                    "created_at": datetime(
                        2026,
                        9,
                        4,
                        12,
                        0,
                        tzinfo=UTC,
                    ),
                }
            ],
        }
    )
    monkeypatch.setattr(
        cat_service,
        "get_cat_conversation_context",
        get_context,
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work

    try:
        response = TestClient(app).get(f"/api/v1/cats/{cat_asset_public_id}/conversation-context")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    get_context.assert_called_once_with(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset_public_id,
    )

    body = response.json()
    assert body["cat_asset_public_id"] == str(cat_asset_public_id)
    assert body["cat_public_id"] == str(cat_public_id)
    assert body["persona"] == "차분하고 다정한 고양이"
    assert body["memories"][0]["public_id"] == str(memory_public_id)

    internal_ids = {"id", "user_id", "cat_id", "cat_asset_id"}
    assert internal_ids.isdisjoint(body)
    assert internal_ids.isdisjoint(body["memories"][0])


def test_get_cat_conversation_context_converts_not_found_to_404(
    monkeypatch,
) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    cat_asset_public_id = uuid.uuid4()

    get_context = MagicMock(side_effect=ResourceNotFoundError("cat asset not found"))
    monkeypatch.setattr(
        cat_service,
        "get_cat_conversation_context",
        get_context,
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work

    try:
        response = TestClient(
            app,
            raise_server_exceptions=False,
        ).get(f"/api/v1/cats/{cat_asset_public_id}/conversation-context")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "cat asset not found",
    }


def test_cat_memory_create_route_is_registered() -> None:
    path = "/api/v1/cats/{cat_asset_public_id}/memories"

    assert path in app.openapi()["paths"]
    assert "post" in app.openapi()["paths"][path]


def test_create_cat_memory_returns_public_response(
    monkeypatch,
) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    cat_asset_public_id = uuid.uuid4()
    memory_public_id = uuid.uuid4()
    context_summary = "사용자는 함수 호출을 이해했다."

    add_memory = MagicMock(
        return_value={
            "public_id": memory_public_id,
            "cat_asset_public_id": cat_asset_public_id,
            "context_summary": context_summary,
            "created_at": datetime(
                2026,
                9,
                4,
                13,
                0,
                tzinfo=UTC,
            ),
        }
    )
    monkeypatch.setattr(
        cat_service,
        "add_cat_memory",
        add_memory,
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work

    try:
        response = TestClient(app).post(
            f"/api/v1/cats/{cat_asset_public_id}/memories",
            json={
                "context_summary": context_summary,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201

    add_memory.assert_called_once_with(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset_public_id,
        context_summary=context_summary,
    )

    body = response.json()
    assert body["public_id"] == str(memory_public_id)
    assert body["cat_asset_public_id"] == str(cat_asset_public_id)
    assert body["context_summary"] == context_summary

    internal_ids = {"id", "user_id", "cat_id", "cat_asset_id"}
    assert internal_ids.isdisjoint(body)


def test_create_cat_memory_converts_not_found_to_404(
    monkeypatch,
) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    cat_asset_public_id = uuid.uuid4()

    add_memory = MagicMock(side_effect=ResourceNotFoundError("cat asset not found"))
    monkeypatch.setattr(
        cat_service,
        "add_cat_memory",
        add_memory,
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work

    try:
        response = TestClient(
            app,
            raise_server_exceptions=False,
        ).post(
            f"/api/v1/cats/{cat_asset_public_id}/memories",
            json={
                "context_summary": "새로운 대화 요약",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "cat asset not found",
    }


def test_create_cat_memory_converts_invalid_summary_to_422(
    monkeypatch,
) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    cat_asset_public_id = uuid.uuid4()

    add_memory = MagicMock(
        side_effect=InvalidMemorySummaryError("context summary must not be blank")
    )
    monkeypatch.setattr(
        cat_service,
        "add_cat_memory",
        add_memory,
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work

    try:
        response = TestClient(
            app,
            raise_server_exceptions=False,
        ).post(
            f"/api/v1/cats/{cat_asset_public_id}/memories",
            json={
                "context_summary": "   ",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": "context summary must not be blank",
    }


def test_selected_cat_memory_delete_route_is_registered() -> None:
    path = "/api/v1/cats/{cat_asset_public_id}/memories/{memory_public_id}"

    assert path in app.openapi()["paths"]
    assert "delete" in app.openapi()["paths"][path]


def test_delete_selected_cat_memory_returns_no_content(
    monkeypatch,
) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    cat_asset_public_id = uuid.uuid4()
    memory_public_id = uuid.uuid4()

    delete_memory = MagicMock()
    monkeypatch.setattr(
        cat_service,
        "delete_cat_memory",
        delete_memory,
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work

    try:
        response = TestClient(app).delete(
            f"/api/v1/cats/{cat_asset_public_id}/memories/{memory_public_id}"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""

    delete_memory.assert_called_once_with(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset_public_id,
        memory_public_id=memory_public_id,
    )


def test_delete_selected_cat_memory_converts_not_found_to_404(
    monkeypatch,
) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    cat_asset_public_id = uuid.uuid4()
    memory_public_id = uuid.uuid4()

    delete_memory = MagicMock(side_effect=ResourceNotFoundError("cat memory not found"))
    monkeypatch.setattr(
        cat_service,
        "delete_cat_memory",
        delete_memory,
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work

    try:
        response = TestClient(
            app,
            raise_server_exceptions=False,
        ).delete(f"/api/v1/cats/{cat_asset_public_id}/memories/{memory_public_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "cat memory not found",
    }


def test_all_cat_memories_delete_route_is_registered() -> None:
    path = "/api/v1/cats/{cat_asset_public_id}/memories"

    assert path in app.openapi()["paths"]
    assert "delete" in app.openapi()["paths"][path]


def test_delete_all_cat_memories_returns_no_content(monkeypatch) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    cat_asset_public_id = uuid.uuid4()
    delete_all_memories = MagicMock()
    monkeypatch.setattr(
        cat_service,
        "delete_all_cat_memories",
        delete_all_memories,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work

    try:
        response = TestClient(app).delete(f"/api/v1/cats/{cat_asset_public_id}/memories")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""
    delete_all_memories.assert_called_once_with(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset_public_id,
    )


def test_delete_all_cat_memories_converts_not_found_to_404(
    monkeypatch,
) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    cat_asset_public_id = uuid.uuid4()
    delete_all_memories = MagicMock(side_effect=ResourceNotFoundError("cat asset not found"))
    monkeypatch.setattr(
        cat_service,
        "delete_all_cat_memories",
        delete_all_memories,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = lambda: unit_of_work

    try:
        response = TestClient(
            app,
            raise_server_exceptions=False,
        ).delete(f"/api/v1/cats/{cat_asset_public_id}/memories")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "cat asset not found"}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", f"/api/v1/cats/{uuid.uuid4()}/memories"),
        (
            "DELETE",
            f"/api/v1/cats/{uuid.uuid4()}/memories/{uuid.uuid4()}",
        ),
        ("DELETE", f"/api/v1/cats/{uuid.uuid4()}/memories"),
    ],
)
def test_cat_memory_changes_require_authentication(
    method: str,
    path: str,
) -> None:
    response = TestClient(app).request(
        method,
        path,
        json={"context_summary": "summary"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"context_summary": "summary", "cat_asset_id": 1},
    ],
)
def test_create_cat_memory_rejects_invalid_request_body(
    monkeypatch,
    payload: dict,
) -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    add_memory = MagicMock()
    monkeypatch.setattr(cat_service, "add_cat_memory", add_memory)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = MagicMock

    try:
        response = TestClient(app).post(
            f"/api/v1/cats/{uuid.uuid4()}/memories",
            json=payload,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    add_memory.assert_not_called()


def test_cat_routes_reject_invalid_public_uuid() -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cat_unit_of_work] = MagicMock

    try:
        response = TestClient(app).get("/api/v1/cats/not-a-uuid/conversation-context")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_cat_response_schemas_exclude_internal_ids() -> None:
    schemas = app.openapi()["components"]["schemas"]
    forbidden = {"id", "user_id", "cat_id", "cat_asset_id"}

    for schema_name in (
        "CatConversationContextRead",
        "CatMemoryRead",
    ):
        properties = set(schemas[schema_name]["properties"])
        assert forbidden.isdisjoint(properties)
