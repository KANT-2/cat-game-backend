"""One-time initialization for a newly created player."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.cat import Cat
from app.models.item import Item
from app.models.placed_object import PlacedObject
from app.models.user import User
from app.modules.game.catalog import (
    STARTER_ACTIVE_CAT_KEY,
    STARTER_CAT_KEYS,
    STARTER_HOME_CAT_KEYS,
    STARTER_ITEM_QUANTITIES,
    STARTER_PACK_VERSION,
    STARTER_PLACEMENTS,
)


class GameCatalogNotSeededError(RuntimeError):
    """Raised when starter state cannot be created from the static catalog."""


def bootstrap_starter_pack(db: Session, user: User) -> bool:
    """Grant the current starter pack exactly once inside the caller's transaction.

    @param db: Active SQLAlchemy session that owns the user instance.
    @param user: Player whose starter pack version is inspected and advanced.
    @returns True when this call added starter state, otherwise false.
    @throws GameCatalogNotSeededError: The database catalog is incomplete.

    @remarks The caller must commit or roll back the transaction.
    """
    if user.starter_pack_version >= STARTER_PACK_VERSION:
        return False

    cats = {
        row.catalog_key: row
        for row in db.scalars(select(Cat).where(Cat.catalog_key.in_(STARTER_CAT_KEYS))).all()
    }
    items = {
        row.catalog_key: row
        for row in db.scalars(
            select(Item).where(Item.catalog_key.in_(tuple(STARTER_ITEM_QUANTITIES)))
        ).all()
    }
    missing_cats = set(STARTER_CAT_KEYS) - cats.keys()
    missing_items = set(STARTER_ITEM_QUANTITIES) - items.keys()
    if missing_cats or missing_items:
        missing = ", ".join(sorted(missing_cats | missing_items))
        raise GameCatalogNotSeededError(f"missing game catalog entries: {missing}")

    existing_cat_ids = set(
        db.scalars(
            select(Asset.cat_id).where(Asset.user_id == user.id, Asset.cat_id.is_not(None))
        ).all()
    )
    for catalog_key in STARTER_CAT_KEYS:
        cat = cats[catalog_key]
        if cat.id in existing_cat_ids:
            continue
        db.add(
            Asset(
                user_id=user.id,
                cat_id=cat.id,
                item_id=None,
                quantity=1,
                is_home=catalog_key in STARTER_HOME_CAT_KEYS,
            )
        )

    existing_item_assets = {
        row.item_id: row
        for row in db.scalars(
            select(Asset).where(Asset.user_id == user.id, Asset.item_id.is_not(None))
        ).all()
    }
    for catalog_key, quantity in STARTER_ITEM_QUANTITIES.items():
        item = items[catalog_key]
        if item.id in existing_item_assets:
            continue
        db.add(
            Asset(
                user_id=user.id,
                cat_id=None,
                item_id=item.id,
                quantity=quantity,
                is_home=False,
            )
        )

    has_placements = db.scalar(
        select(PlacedObject.id).where(PlacedObject.user_id == user.id).limit(1)
    )
    if has_placements is None:
        for catalog_key, x, y, rotation in STARTER_PLACEMENTS:
            db.add(
                PlacedObject(
                    user_id=user.id,
                    item_id=items[catalog_key].id,
                    position_data={"x": x, "y": y, "z": rotation},
                )
            )

    user.active_cat_id = cats[STARTER_ACTIVE_CAT_KEY].id
    user.starter_pack_version = STARTER_PACK_VERSION
    user.advance_state_version()
    return True
