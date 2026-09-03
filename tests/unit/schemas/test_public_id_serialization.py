import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.schemas.asset import to_asset_read
from app.schemas.cat_memory import to_cat_memory_read
from app.schemas.placed_object import to_placed_object_read


def test_to_asset_read_uses_public_ids() -> None:
    asset_public_id = uuid.uuid4()
    cat_public_id = uuid.uuid4()

    asset = SimpleNamespace(
        public_id=asset_public_id,
        quantity=1,
    )

    result = to_asset_read(
        asset,
        cat_public_id=cat_public_id,
        item_public_id=None,
    )

    assert result.public_id == asset_public_id
    assert result.cat_public_id == cat_public_id
    assert result.item_public_id is None
    assert result.quantity == 1
    assert "id" not in result.model_dump()


def test_to_asset_read_maps_item_public_id() -> None:
    asset_public_id = uuid.uuid4()
    item_public_id = uuid.uuid4()

    asset = SimpleNamespace(
        public_id=asset_public_id,
        quantity=3,
    )

    result = to_asset_read(
        asset,
        cat_public_id=None,
        item_public_id=item_public_id,
    )

    assert result.public_id == asset_public_id
    assert result.cat_public_id is None
    assert result.item_public_id == item_public_id
    assert result.quantity == 3
    assert "id" not in result.model_dump()


def test_to_placed_object_read_uses_item_public_id() -> None:
    placed_object_public_id = uuid.uuid4()
    item_public_id = uuid.uuid4()
    position_data = {
        "x": 120,
        "y": 80,
        "z": 0,
    }

    placed_object = SimpleNamespace(
        public_id=placed_object_public_id,
        position_data=position_data,
    )

    result = to_placed_object_read(
        placed_object,
        item_public_id=item_public_id,
    )

    assert result.public_id == placed_object_public_id
    assert result.item_public_id == item_public_id
    assert result.position_data == position_data
    assert "id" not in result.model_dump()


def test_to_cat_memory_read_uses_cat_asset_public_id() -> None:
    memory_public_id = uuid.uuid4()
    cat_asset_public_id = uuid.uuid4()
    created_at = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)

    memory = SimpleNamespace(
        public_id=memory_public_id,
        context_summary="사용자는 반복문 문제를 어려워한다.",
        created_at=created_at,
    )

    result = to_cat_memory_read(
        memory,
        cat_asset_public_id=cat_asset_public_id,
    )

    assert result.public_id == memory_public_id
    assert result.cat_asset_public_id == cat_asset_public_id
    assert result.context_summary == "사용자는 반복문 문제를 어려워한다."
    assert result.created_at == created_at
    assert "id" not in result.model_dump()
