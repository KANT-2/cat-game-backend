import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.exceptions import (
    InvalidItemCategoryError,
    PlacementLimitExceededError,
    ResourceNotFoundError,
)
from app.main import app
from app.modules.housing import service as housing_service
from app.modules.housing.router import get_housing_unit_of_work


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client():
    user = SimpleNamespace(public_id=uuid.uuid4())
    unit_of_work = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_housing_unit_of_work] = lambda: unit_of_work

    return TestClient(app), user, unit_of_work


def test_apply_surface_requires_authentication() -> None:
    response = TestClient(app).put(f"/api/v1/housing/surfaces/{uuid.uuid4()}")

    assert response.status_code == 401


def test_apply_surface_returns_public_response(
    monkeypatch,
    authenticated_client,
) -> None:
    client, user, unit_of_work = authenticated_client
    item_public_id = uuid.uuid4()

    apply_surface_item = MagicMock(
        return_value={
            "user_public_id": user.public_id,
            "item_public_id": item_public_id,
            "category": "WALLPAPER",
        }
    )
    monkeypatch.setattr(
        housing_service,
        "apply_surface_item",
        apply_surface_item,
    )

    response = client.put(f"/api/v1/housing/surfaces/{item_public_id}")

    assert response.status_code == 200

    apply_surface_item.assert_called_once_with(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        item_public_id=item_public_id,
    )

    body = response.json()
    assert body["user_public_id"] == str(user.public_id)
    assert body["item_public_id"] == str(item_public_id)
    assert body["category"] == "WALLPAPER"

    internal_ids = {
        "id",
        "user_id",
        "item_id",
        "wallpaper_item_id",
        "floor_item_id",
    }
    assert internal_ids.isdisjoint(body)


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ResourceNotFoundError("item not found"), 404),
        (
            InvalidItemCategoryError("item is not wallpaper or floor"),
            422,
        ),
    ],
)
def test_apply_surface_converts_domain_errors(
    monkeypatch,
    authenticated_client,
    error,
    expected_status: int,
) -> None:
    client, _, _ = authenticated_client

    monkeypatch.setattr(
        housing_service,
        "apply_surface_item",
        MagicMock(side_effect=error),
    )

    response = client.put(f"/api/v1/housing/surfaces/{uuid.uuid4()}")

    assert response.status_code == expected_status
    assert response.json() == {
        "detail": str(error),
    }


def test_apply_surface_rejects_invalid_item_uuid(
    authenticated_client,
) -> None:
    client, _, _ = authenticated_client

    response = client.put("/api/v1/housing/surfaces/not-a-uuid")

    assert response.status_code == 422


def test_place_furniture_returns_public_response(
    monkeypatch,
    authenticated_client,
) -> None:
    client, user, unit_of_work = authenticated_client
    item_public_id = uuid.uuid4()
    placed_object_public_id = uuid.uuid4()
    position = {"x": 10.0, "y": 20.0, "z": 30.0}

    place = MagicMock(
        return_value={
            "public_id": placed_object_public_id,
            "item_public_id": item_public_id,
            "position_data": position,
        }
    )
    monkeypatch.setattr(
        housing_service,
        "place_furniture",
        place,
    )

    response = client.post(
        "/api/v1/housing/placed-objects",
        json={
            "item_public_id": str(item_public_id),
            "position_data": position,
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "public_id": str(placed_object_public_id),
        "item_public_id": str(item_public_id),
        "position_data": position,
    }

    call = place.call_args.kwargs
    assert call["unit_of_work"] is unit_of_work
    assert call["user_public_id"] == user.public_id
    assert call["item_public_id"] == item_public_id
    assert call["position_data"].model_dump() == position


def test_update_furniture_returns_public_response(
    monkeypatch,
    authenticated_client,
) -> None:
    client, user, unit_of_work = authenticated_client
    placed_object_public_id = uuid.uuid4()
    item_public_id = uuid.uuid4()
    position = {"x": 15.0, "y": 25.0, "z": 35.0}

    update = MagicMock(
        return_value={
            "public_id": placed_object_public_id,
            "item_public_id": item_public_id,
            "position_data": position,
        }
    )
    monkeypatch.setattr(
        housing_service,
        "update_furniture_placement",
        update,
    )

    response = client.patch(
        (f"/api/v1/housing/placed-objects/{placed_object_public_id}"),
        json={"position_data": position},
    )

    assert response.status_code == 200
    assert response.json()["public_id"] == str(placed_object_public_id)
    assert response.json()["item_public_id"] == str(item_public_id)

    call = update.call_args.kwargs
    assert call["unit_of_work"] is unit_of_work
    assert call["user_public_id"] == user.public_id
    assert call["placed_object_public_id"] == (placed_object_public_id)
    assert call["position_data"].model_dump() == position


def test_remove_furniture_returns_no_content(
    monkeypatch,
    authenticated_client,
) -> None:
    client, user, unit_of_work = authenticated_client
    placed_object_public_id = uuid.uuid4()
    remove = MagicMock()

    monkeypatch.setattr(
        housing_service,
        "remove_furniture_placement",
        remove,
    )

    response = client.delete(f"/api/v1/housing/placed-objects/{placed_object_public_id}")

    assert response.status_code == 204
    assert response.content == b""

    remove.assert_called_once_with(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        placed_object_public_id=placed_object_public_id,
    )


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ResourceNotFoundError("item not found"), 404),
        (
            InvalidItemCategoryError("item is not furniture"),
            422,
        ),
        (
            PlacementLimitExceededError("placement exceeds owned quantity"),
            409,
        ),
    ],
)
def test_place_furniture_converts_domain_errors(
    monkeypatch,
    authenticated_client,
    error,
    expected_status: int,
) -> None:
    client, _, _ = authenticated_client
    monkeypatch.setattr(
        housing_service,
        "place_furniture",
        MagicMock(side_effect=error),
    )

    response = client.post(
        "/api/v1/housing/placed-objects",
        json={
            "item_public_id": str(uuid.uuid4()),
            "position_data": {
                "x": 10,
                "y": 20,
                "z": 30,
            },
        },
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


@pytest.mark.parametrize(
    ("method", "service_name"),
    [
        ("PATCH", "update_furniture_placement"),
        ("DELETE", "remove_furniture_placement"),
    ],
)
def test_existing_furniture_changes_convert_not_found_to_404(
    monkeypatch,
    authenticated_client,
    method: str,
    service_name: str,
) -> None:
    client, _, _ = authenticated_client
    monkeypatch.setattr(
        housing_service,
        service_name,
        MagicMock(side_effect=ResourceNotFoundError("placed object not found")),
    )
    placed_object_public_id = uuid.uuid4()
    request_kwargs = {}

    if method == "PATCH":
        request_kwargs["json"] = {
            "position_data": {
                "x": 10,
                "y": 20,
                "z": 30,
            }
        }

    response = client.request(
        method,
        (f"/api/v1/housing/placed-objects/{placed_object_public_id}"),
        **request_kwargs,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "placed object not found",
    }


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "POST",
            "/api/v1/housing/placed-objects",
            {
                "item_public_id": str(uuid.uuid4()),
                "position_data": {
                    "x": 10,
                    "y": 20,
                    "z": 30,
                },
            },
        ),
        (
            "PATCH",
            (f"/api/v1/housing/placed-objects/{uuid.uuid4()}"),
            {
                "position_data": {
                    "x": 10,
                    "y": 20,
                    "z": 30,
                },
            },
        ),
        (
            "DELETE",
            (f"/api/v1/housing/placed-objects/{uuid.uuid4()}"),
            None,
        ),
    ],
)
def test_furniture_changes_require_authentication(
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    request_kwargs = {}

    if payload is not None:
        request_kwargs["json"] = payload

    response = TestClient(app).request(
        method,
        path,
        **request_kwargs,
    )

    assert response.status_code == 401
