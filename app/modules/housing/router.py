import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import CurrentUser
from app.core.exceptions import (
    InvalidItemCategoryError,
    PlacementLimitExceededError,
    ResourceNotFoundError,
)
from app.core.unit_of_work import UnitOfWork
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.housing import service as housing_service
from app.schemas.housing import SurfaceApplicationRead
from app.schemas.placed_object import (
    PlacedObjectCreate,
    PlacedObjectRead,
    PlacedObjectUpdate,
)

router = APIRouter(prefix="/housing", tags=["housing"])


def get_housing_unit_of_work() -> UnitOfWork:
    return SqlAlchemyUnitOfWork()


HousingUnitOfWork = Annotated[
    UnitOfWork,
    Depends(get_housing_unit_of_work),
]


@router.put(
    "/surfaces/{item_public_id}",
    response_model=SurfaceApplicationRead,
)
def apply_surface(
    item_public_id: uuid.UUID,
    current_user: CurrentUser,
    unit_of_work: HousingUnitOfWork,
) -> SurfaceApplicationRead:
    try:
        return housing_service.apply_surface_item(
            unit_of_work=unit_of_work,
            user_public_id=current_user.public_id,
            item_public_id=item_public_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidItemCategoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.post(
    "/placed-objects",
    response_model=PlacedObjectRead,
    status_code=status.HTTP_201_CREATED,
)
def place_furniture(
    payload: PlacedObjectCreate,
    current_user: CurrentUser,
    unit_of_work: HousingUnitOfWork,
) -> PlacedObjectRead:
    try:
        return housing_service.place_furniture(
            unit_of_work=unit_of_work,
            user_public_id=current_user.public_id,
            item_public_id=payload.item_public_id,
            position_data=payload.position_data,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidItemCategoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except PlacementLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.patch(
    "/placed-objects/{placed_object_public_id}",
    response_model=PlacedObjectRead,
)
def update_furniture_placement(
    placed_object_public_id: uuid.UUID,
    payload: PlacedObjectUpdate,
    current_user: CurrentUser,
    unit_of_work: HousingUnitOfWork,
) -> PlacedObjectRead:
    try:
        return housing_service.update_furniture_placement(
            unit_of_work=unit_of_work,
            user_public_id=current_user.public_id,
            placed_object_public_id=placed_object_public_id,
            position_data=payload.position_data,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/placed-objects/{placed_object_public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_furniture_placement(
    placed_object_public_id: uuid.UUID,
    current_user: CurrentUser,
    unit_of_work: HousingUnitOfWork,
) -> None:
    try:
        housing_service.remove_furniture_placement(
            unit_of_work=unit_of_work,
            user_public_id=current_user.public_id,
            placed_object_public_id=placed_object_public_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
