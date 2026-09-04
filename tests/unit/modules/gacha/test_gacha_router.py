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
from app.modules.gacha import service as gacha_service
from app.modules.gacha.router import (
    get_gacha_policy,
    get_gacha_unit_of_work,
)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client():
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()
    policy = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_gacha_unit_of_work] = lambda: unit_of_work
    app.dependency_overrides[get_gacha_policy] = lambda: policy

    return TestClient(app), user, unit_of_work, policy


def test_gacha_requires_authentication() -> None:
    response = TestClient(app).post(
        "/api/v1/gacha/draws",
        json={
            "request_id": str(uuid.uuid4()),
            "draw_count": 1,
        },
    )

    assert response.status_code == 401


def test_gacha_returns_503_when_policy_is_not_configured() -> None:
    user = SimpleNamespace(public_id=uuid.uuid4())

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_gacha_unit_of_work] = MagicMock

    response = TestClient(app).post(
        "/api/v1/gacha/draws",
        json={
            "request_id": str(uuid.uuid4()),
            "draw_count": 1,
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Gacha policy is not configured",
    }


@pytest.mark.parametrize("draw_count", [1, 10])
def test_gacha_returns_public_response_for_supported_draw_count(
    monkeypatch,
    authenticated_client,
    draw_count: int,
) -> None:
    client, user, unit_of_work, policy = authenticated_client
    request_id = uuid.uuid4()
    execution_public_id = uuid.uuid4()
    cat_public_id = uuid.uuid4()
    bonus_draw_count = 1 if draw_count == 10 else 0
    result_count = draw_count + bonus_draw_count

    draw = MagicMock(
        return_value={
            "execution_public_id": str(execution_public_id),
            "request_id": str(request_id),
            "draw_count": draw_count,
            "bonus_draw_count": bonus_draw_count,
            "balance_cost": 200 * draw_count,
            "balance": 800,
            "mileage": 0,
            "results": [
                {
                    "cat_public_id": str(cat_public_id),
                    "name": "나비",
                    "rarity": "COMMON",
                    "is_duplicate": False,
                    "mileage_awarded": 0,
                }
                for _ in range(result_count)
            ],
        }
    )
    monkeypatch.setattr(
        gacha_service,
        "draw_cats",
        draw,
    )

    response = client.post(
        "/api/v1/gacha/draws",
        json={
            "request_id": str(request_id),
            "draw_count": draw_count,
        },
    )

    assert response.status_code == 200

    draw.assert_called_once_with(
        unit_of_work=unit_of_work,
        policy=policy,
        user_public_id=user.public_id,
        request_id=request_id,
        draw_count=draw_count,
    )

    body = response.json()
    assert body["execution_public_id"] == str(execution_public_id)
    assert body["request_id"] == str(request_id)
    assert body["draw_count"] == draw_count
    assert body["bonus_draw_count"] == bonus_draw_count
    assert len(body["results"]) == result_count
    assert body["results"][0]["cat_public_id"] == str(cat_public_id)

    internal_ids = {"id", "user_id", "cat_id", "asset_id"}
    assert internal_ids.isdisjoint(body)
    assert internal_ids.isdisjoint(body["results"][0])


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ResourceNotFoundError("cat not found"), 404),
        (IdempotencyConflictError("request_id conflict"), 409),
        (InsufficientBalanceError("insufficient balance"), 409),
        (
            InvalidQuantityError("draw_count must be positive"),
            422,
        ),
    ],
)
def test_gacha_converts_domain_errors(
    monkeypatch,
    authenticated_client,
    error,
    expected_status: int,
) -> None:
    client, _, _, _ = authenticated_client
    monkeypatch.setattr(
        gacha_service,
        "draw_cats",
        MagicMock(side_effect=error),
    )

    response = client.post(
        "/api/v1/gacha/draws",
        json={
            "request_id": str(uuid.uuid4()),
            "draw_count": 1,
        },
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


@pytest.mark.parametrize(
    "payload",
    [
        {
            "request_id": str(uuid.uuid4()),
            "draw_count": 0,
        },
        {
            "request_id": str(uuid.uuid4()),
            "draw_count": 2,
        },
        {
            "request_id": str(uuid.uuid4()),
            "draw_count": 1,
            "balance_cost": 200,
        },
    ],
)
def test_gacha_rejects_invalid_request(
    monkeypatch,
    authenticated_client,
    payload: dict,
) -> None:
    client, _, _, _ = authenticated_client
    draw = MagicMock()
    monkeypatch.setattr(gacha_service, "draw_cats", draw)

    response = client.post(
        "/api/v1/gacha/draws",
        json=payload,
    )

    assert response.status_code == 422
    draw.assert_not_called()
