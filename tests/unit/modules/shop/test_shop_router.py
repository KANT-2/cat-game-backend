import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.exceptions import (
    IdempotencyConflictError,
    InsufficientBalanceError,
    InvalidQuantityError,
    ResourceNotFoundError,
)
from app.main import app
from app.modules.shop import service as shop_service
from app.modules.shop.router import get_shop_unit_of_work


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client():
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_shop_unit_of_work] = lambda: unit_of_work

    return TestClient(app), user, unit_of_work


def test_purchase_requires_authentication() -> None:
    response = TestClient(app).post(
        "/api/v1/shop/purchases",
        json={
            "request_id": str(uuid.uuid4()),
            "item_public_id": str(uuid.uuid4()),
            "quantity": 1,
        },
    )

    assert response.status_code == 401


def test_purchase_returns_public_response(
    monkeypatch,
    authenticated_client,
) -> None:
    client, user, unit_of_work = authenticated_client
    request_id = uuid.uuid4()
    item_public_id = uuid.uuid4()
    execution_public_id = uuid.uuid4()

    purchase = MagicMock(
        return_value={
            "execution_public_id": str(execution_public_id),
            "request_id": str(request_id),
            "item_public_id": str(item_public_id),
            "purchased_quantity": 2,
            "total_quantity": 5,
            "balance": 700,
        }
    )
    monkeypatch.setattr(
        shop_service,
        "purchase_item",
        purchase,
    )

    response = client.post(
        "/api/v1/shop/purchases",
        json={
            "request_id": str(request_id),
            "item_public_id": str(item_public_id),
            "quantity": 2,
        },
    )

    assert response.status_code == 201

    purchase.assert_called_once_with(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        request_id=request_id,
        item_public_id=item_public_id,
        quantity=2,
    )

    body = response.json()
    assert body["execution_public_id"] == str(execution_public_id)
    assert body["request_id"] == str(request_id)
    assert body["item_public_id"] == str(item_public_id)
    assert body["purchased_quantity"] == 2
    assert body["total_quantity"] == 5
    assert body["balance"] == 700

    internal_ids = {"id", "user_id", "item_id", "asset_id"}
    assert internal_ids.isdisjoint(body)


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ResourceNotFoundError("item not found"), 404),
        (IdempotencyConflictError("request_id conflict"), 409),
        (InsufficientBalanceError("insufficient balance"), 409),
        (InvalidQuantityError("quantity must be positive"), 422),
    ],
)
def test_purchase_converts_domain_errors(
    monkeypatch,
    authenticated_client,
    error,
    expected_status: int,
) -> None:
    client, _, _ = authenticated_client

    monkeypatch.setattr(
        shop_service,
        "purchase_item",
        MagicMock(side_effect=error),
    )

    response = client.post(
        "/api/v1/shop/purchases",
        json={
            "request_id": str(uuid.uuid4()),
            "item_public_id": str(uuid.uuid4()),
            "quantity": 1,
        },
    )

    assert response.status_code == expected_status
    assert response.json() == {
        "detail": str(error),
    }


@pytest.mark.parametrize(
    "payload",
    [
        {
            "request_id": str(uuid.uuid4()),
            "item_public_id": str(uuid.uuid4()),
            "quantity": 0,
        },
        {
            "request_id": str(uuid.uuid4()),
            "item_public_id": str(uuid.uuid4()),
            "quantity": 1,
            "price": 100,
        },
    ],
)
def test_purchase_rejects_invalid_request(
    monkeypatch,
    authenticated_client,
    payload: dict,
) -> None:
    client, _, _ = authenticated_client
    purchase = MagicMock()
    monkeypatch.setattr(
        shop_service,
        "purchase_item",
        purchase,
    )

    response = client.post(
        "/api/v1/shop/purchases",
        json=payload,
    )

    assert response.status_code == 422
    purchase.assert_not_called()
