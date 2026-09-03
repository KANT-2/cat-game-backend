import math
import uuid

import pytest
from pydantic import ValidationError

from app.schemas.placed_object import (
    PlacedObjectCreate,
    PositionData,
)


def test_placed_object_create_accepts_finite_position() -> None:
    item_public_id = uuid.uuid4()

    request = PlacedObjectCreate(
        item_public_id=item_public_id,
        position_data={
            "x": 120,
            "y": 80,
            "z": 45,
        },
    )

    assert request.item_public_id == item_public_id
    assert request.position_data == PositionData(
        x=120,
        y=80,
        z=45,
    )


@pytest.mark.parametrize("missing_field", ["x", "y", "z"])
def test_position_data_requires_every_field(
    missing_field: str,
) -> None:
    position_data = {
        "x": 120,
        "y": 80,
        "z": 45,
    }
    del position_data[missing_field]

    with pytest.raises(ValidationError):
        PositionData(**position_data)


@pytest.mark.parametrize(
    "invalid_value",
    [math.nan, math.inf, -math.inf],
)
def test_position_data_rejects_nonfinite_numbers(
    invalid_value: float,
) -> None:
    with pytest.raises(ValidationError):
        PositionData(
            x=invalid_value,
            y=80,
            z=45,
        )


def test_position_data_rejects_legacy_rotation_field() -> None:
    with pytest.raises(ValidationError):
        PositionData(x=120, y=80, z=45, rotation=45)
