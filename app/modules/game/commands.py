"""Small authoritative commands not covered by economy or housing services."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.models.asset import Asset
from app.models.cat import Cat
from app.models.user import User


def select_active_cat(db: Session, user: User, catalog_key: str) -> None:
    """Select an owned cat and make it visible at home in one transaction."""
    cat = db.scalar(select(Cat).where(Cat.catalog_key == catalog_key))
    if cat is None:
        raise ResourceNotFoundError("cat not found")
    asset = db.scalar(
        select(Asset)
        .where(Asset.user_id == user.id, Asset.cat_id == cat.id)
        .with_for_update()
    )
    if asset is None:
        raise ResourceNotFoundError("cat asset not found")
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")
    asset.is_home = True
    locked_user.active_cat_id = cat.id
    db.commit()


def set_cat_home(db: Session, user: User, catalog_key: str, *, visible: bool) -> None:
    """Change an owned cat's home visibility and keep the active selection valid."""
    cat = db.scalar(select(Cat).where(Cat.catalog_key == catalog_key))
    if cat is None:
        raise ResourceNotFoundError("cat not found")
    asset = db.scalar(
        select(Asset)
        .where(Asset.user_id == user.id, Asset.cat_id == cat.id)
        .with_for_update()
    )
    if asset is None:
        raise ResourceNotFoundError("cat asset not found")
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ResourceNotFoundError("user not found")
    asset.is_home = visible
    if not visible and locked_user.active_cat_id == cat.id:
        replacement = db.scalar(
            select(Asset)
            .where(
                Asset.user_id == user.id,
                Asset.cat_id.is_not(None),
                Asset.is_home.is_(True),
                Asset.id != asset.id,
            )
            .order_by(Asset.id)
            .limit(1)
        )
        if replacement is not None:
            locked_user.active_cat_id = replacement.cat_id
    db.commit()
