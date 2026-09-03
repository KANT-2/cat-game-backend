import uuid
from typing import Protocol

from app.schemas.base import ReadSchema


class _AssetReadSource(Protocol):
    public_id: uuid.UUID
    quantity: int


class AssetRead(ReadSchema):
    cat_public_id: uuid.UUID | None
    item_public_id: uuid.UUID | None
    quantity: int


def to_asset_read(
    asset: _AssetReadSource,
    *,
    cat_public_id: uuid.UUID | None,
    item_public_id: uuid.UUID | None,
) -> AssetRead:
    return AssetRead(
        public_id=asset.public_id,
        cat_public_id=cat_public_id,
        item_public_id=item_public_id,
        quantity=asset.quantity,
    )
