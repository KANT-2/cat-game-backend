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
from app.modules.gacha import service as gacha_service
from app.modules.gacha.policy import GachaPolicy
from app.schemas.gacha import GachaRequest, GachaResponse

router = APIRouter(prefix="/gacha", tags=["gacha"])


def get_gacha_unit_of_work() -> UnitOfWork:
    return SqlAlchemyUnitOfWork()


def get_gacha_policy() -> GachaPolicy:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Gacha policy is not configured",
    )


GachaUnitOfWork = Annotated[
    UnitOfWork,
    Depends(get_gacha_unit_of_work),
]

GachaPolicyDependency = Annotated[
    GachaPolicy,
    Depends(get_gacha_policy),
]


@router.post(
    "/draws",
    response_model=GachaResponse,
)
def draw_cats(
    payload: GachaRequest,
    current_user: CurrentUser,
    unit_of_work: GachaUnitOfWork,
    policy: GachaPolicyDependency,
) -> GachaResponse:
    try:
        return gacha_service.draw_cats(
            unit_of_work=unit_of_work,
            policy=policy,
            user_public_id=current_user.public_id,
            request_id=payload.request_id,
            draw_count=payload.draw_count,
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
