from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import CurrentUser
from app.core.exceptions import (
    IdempotencyConflictError,
    InsufficientBalanceError,
    InvalidQuantityError,
    ResourceNotFoundError,
)
from app.core.unit_of_work import UnitOfWork
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.shop import service as shop_service
from app.schemas.purchase import PurchaseRequest, PurchaseResponse

router = APIRouter(prefix="/shop", tags=["shop"])


def get_shop_unit_of_work() -> UnitOfWork:
    return SqlAlchemyUnitOfWork()


ShopUnitOfWork = Annotated[
    UnitOfWork,
    Depends(get_shop_unit_of_work),
]


@router.post(
    "/purchases",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def purchase_item(
    payload: PurchaseRequest,
    current_user: CurrentUser,
    unit_of_work: ShopUnitOfWork,
) -> PurchaseResponse:
    try:
        return shop_service.purchase_item(
            unit_of_work=unit_of_work,
            user_public_id=current_user.public_id,
            request_id=payload.request_id,
            item_public_id=payload.item_public_id,
            quantity=payload.quantity,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        IdempotencyConflictError,
        InsufficientBalanceError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidQuantityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
