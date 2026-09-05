from uuid import UUID

from app.core.exceptions import (
    IdempotencyConflictError,
    InvalidItemCategoryError,
    PlacementLimitExceededError,
    PlacementOccupiedError,
    PlacementOutsideRoomError,
    ResourceNotFoundError,
)
from app.core.unit_of_work import UnitOfWork
from app.models.item import Item
from app.models.placed_object import PlacedObject
from app.modules.game.catalog import ITEM_BY_KEY, ROOM_GRID_HEIGHT, ROOM_GRID_WIDTH
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
    placement_public_id: UUID | None = None,
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

        if placement_public_id is not None:
            existing = uow.placed_objects.get_by_public_id_for_update(placement_public_id)
            if existing is not None:
                expected_position = position_data.model_dump(mode="json")
                if (
                    existing.user_id != user.id
                    or existing.item_id != item.id
                    or existing.position_data != expected_position
                ):
                    raise IdempotencyConflictError("placement_public_id conflict")
                return to_placed_object_read(existing, item_public_id=item.public_id)

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

        _ensure_placement_free(
            unit_of_work=uow,
            user_id=user.id,
            item=item,
            position_data=position_data,
        )

        placed_object = uow.placed_objects.add(
            user.id,
            item.id,
            position_data.model_dump(mode="json"),
            public_id=placement_public_id,
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

        _ensure_placement_free(
            unit_of_work=uow,
            user_id=user.id,
            item=item,
            position_data=position_data,
            excluded=placed_object,
        )

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


def _ensure_placement_free(
    *,
    unit_of_work: UnitOfWork,
    user_id: int,
    item: Item,
    position_data: PositionData,
    excluded: PlacedObject | None = None,
) -> None:
    definition = ITEM_BY_KEY.get(item.catalog_key)
    if definition is None or definition.width is None or definition.height is None:
        return

    x = position_data.x
    y = position_data.y
    rotation = position_data.z
    if not x.is_integer() or not y.is_integer() or rotation not in {0, 1}:
        raise PlacementOutsideRoomError("game placement must use integer grid coordinates")

    width, height = definition.width, definition.height
    if rotation == 1:
        width, height = height, width
    if x < 0 or y < 0 or x + width > ROOM_GRID_WIDTH or y + height > ROOM_GRID_HEIGHT:
        raise PlacementOutsideRoomError("placement is outside the room")

    for placed in unit_of_work.placed_objects.list_for_update(user_id):
        if excluded is not None and placed.id == excluded.id:
            continue
        other_item = unit_of_work.items.get_by_id(placed.item_id)
        if other_item is None:
            raise ResourceNotFoundError("placed item not found")
        other_definition = ITEM_BY_KEY.get(other_item.catalog_key)
        if other_definition is None or other_definition.width is None or other_definition.height is None:
            continue
        other_x = float(placed.position_data["x"])
        other_y = float(placed.position_data["y"])
        other_rotation = int(placed.position_data["z"])
        other_width, other_height = other_definition.width, other_definition.height
        if other_rotation == 1:
            other_width, other_height = other_height, other_width
        overlaps = (
            x < other_x + other_width
            and x + width > other_x
            and y < other_y + other_height
            and y + height > other_y
        )
        if overlaps:
            raise PlacementOccupiedError("placement overlaps another object")
