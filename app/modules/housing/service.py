from uuid import UUID

from app.core.exceptions import (
    InvalidItemCategoryError,
    PlacementLimitExceededError,
    ResourceNotFoundError,
)
from app.core.unit_of_work import UnitOfWork
from app.schemas.housing import SurfaceApplicationRead
from app.schemas.placed_object import (
    PlacedObjectRead,
    PositionData,
    to_placed_object_read,
)


def apply_surface_item(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    item_public_id: UUID,
) -> SurfaceApplicationRead:
    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")

        item = uow.items.get_by_public_id(item_public_id)
        if item is None:
            raise ResourceNotFoundError("item not found")

        if item.category not in {"WALLPAPER", "FLOOR"}:
            raise InvalidItemCategoryError(
                "item is not wallpaper or floor"
            )

        asset = uow.assets.get_item_asset_for_update(
            user.id,
            item.id,
        )
        if asset is None:
            raise ResourceNotFoundError("item asset not found")

        locked_user = uow.users.get_for_update(user.id)
        if locked_user is None:
            raise ResourceNotFoundError("user not found")

        if item.category == "WALLPAPER":
            locked_user.wallpaper_item_id = item.id
        else:
            locked_user.floor_item_id = item.id

        uow.commit()

        return SurfaceApplicationRead(
            user_public_id=locked_user.public_id,
            item_public_id=item.public_id,
            category=item.category,
        )

def place_furniture(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    item_public_id: UUID,
    position_data: PositionData,
) -> PlacedObjectRead:
    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")

        item = uow.items.get_by_public_id(item_public_id)
        if item is None:
            raise ResourceNotFoundError("item not found")
        
        if item.category != "FURNITURE":
            raise InvalidItemCategoryError("item is not furniture")

        asset = uow.assets.get_item_asset_for_update(
            user.id,
            item.id,
        )
        if asset is None:
            raise ResourceNotFoundError("item asset not found")

        placed_count = uow.placed_objects.count_for_update(
            user.id,
            item.id,
        )
        if placed_count >= asset.quantity:
            raise PlacementLimitExceededError(
                "placement exceeds owned quantity"
            )

        placed_object = uow.placed_objects.add(
            user.id,
            item.id,
            position_data.model_dump(mode="json"),
        )

        uow.commit()

        return to_placed_object_read(
            placed_object,
            item_public_id=item.public_id,
        )

def update_furniture_placement(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    placed_object_public_id: UUID,
    position_data: PositionData,
) -> PlacedObjectRead:
    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")

        placed_object = (
            uow.placed_objects.get_by_public_id_for_update(
                placed_object_public_id
            )
        )
        if (
            placed_object is None
            or placed_object.user_id != user.id
        ):
            raise ResourceNotFoundError("placed object not found")

        item = uow.items.get_by_id(placed_object.item_id)
        if item is None:
            raise ResourceNotFoundError("item not found")

        placed_object.position_data = position_data.model_dump(
            mode="json"
        )

        uow.commit()

        return to_placed_object_read(
            placed_object,
            item_public_id=item.public_id,
        )

def remove_furniture_placement(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    placed_object_public_id: UUID,
) -> None:
    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")

        placed_object = (
            uow.placed_objects.get_by_public_id_for_update(
                placed_object_public_id
            )
        )
        if (
            placed_object is None
            or placed_object.user_id != user.id
        ):
            raise ResourceNotFoundError("placed object not found")

        uow.placed_objects.remove(placed_object)
        uow.commit()
