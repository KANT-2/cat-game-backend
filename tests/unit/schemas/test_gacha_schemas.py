import uuid

import pytest
from pydantic import ValidationError

from app.schemas.gacha import (
    GachaDrawResult,
    GachaRequest,
    GachaResponse,
)


@pytest.mark.parametrize("draw_count", [1, 10])
def test_gacha_request_accepts_supported_draw_count(
    draw_count: int,
) -> None:
    request_id = uuid.uuid4()

    request = GachaRequest(
        request_id=request_id,
        draw_count=draw_count,
    )

    assert request.request_id == request_id
    assert request.draw_count == draw_count


@pytest.mark.parametrize("draw_count", [0, -1, 2, 11])
def test_gacha_request_rejects_unsupported_draw_count(
    draw_count: int,
) -> None:
    with pytest.raises(ValidationError):
        GachaRequest(
            request_id=uuid.uuid4(),
            draw_count=draw_count,
        )


def test_gacha_response_exposes_only_public_ids() -> None:
    execution_public_id = uuid.uuid4()
    request_id = uuid.uuid4()
    cat_public_id = uuid.uuid4()

    response = GachaResponse(
        execution_public_id=execution_public_id,
        request_id=request_id,
        draw_count=1,
        bonus_draw_count=0,
        balance_cost=100,
        balance=900,
        mileage=20,
        results=[
            GachaDrawResult(
                cat_public_id=cat_public_id,
                name="Nabi",
                rarity="COMMON",
                is_duplicate=True,
                mileage_awarded=20,
            )
        ],
    )

    dumped = response.model_dump()

    assert dumped["execution_public_id"] == execution_public_id
    assert dumped["results"][0]["cat_public_id"] == cat_public_id
    assert "id" not in dumped
    assert "user_id" not in dumped
    assert "cat_id" not in dumped["results"][0]
