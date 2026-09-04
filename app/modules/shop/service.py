from uuid import UUID

from app.core.exceptions import (
    IdempotencyConflictError,
    InsufficientBalanceError,
    InvalidQuantityError,
    ResourceNotFoundError,
)
from app.core.repository_contracts import ClaimStatus
from app.core.request_hash import build_request_hash
from app.core.unit_of_work import UnitOfWork

_OPERATION_TYPE = "ITEM_PURCHASE"


def purchase_item(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    request_id: UUID,
    item_public_id: UUID,
    quantity: int,
) -> dict[str, object]:
    if quantity <= 0:
        raise InvalidQuantityError("quantity must be positive")

    request_payload: dict[str, object] = {
        "item_public_id": str(item_public_id),
        "quantity": quantity,
    }
    request_hash = build_request_hash(
        operation_type=_OPERATION_TYPE,
        payload=request_payload,
    )

    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")

        claim = uow.executions.claim(
            user_id=user.id,
            request_id=request_id,
            request_hash=request_hash,
            request_payload=request_payload,
            operation_type=_OPERATION_TYPE,
        )
        if claim.status == ClaimStatus.HASH_CONFLICT:
            raise IdempotencyConflictError("request_id conflict")

        if claim.status == ClaimStatus.COMPLETED:
            result_data = claim.execution.result_data
            if result_data is None:
                raise RuntimeError("completed execution has no result data")

            return dict(result_data)

        item = uow.items.get_by_public_id(item_public_id)
        if item is None:
            raise ResourceNotFoundError("item not found")

        locked_user = uow.users.get_for_update(user.id)
        if locked_user is None:
            raise ResourceNotFoundError("user not found")

        balance_cost = item.price * quantity
        if locked_user.balance < balance_cost:
            raise InsufficientBalanceError("insufficient balance")

        locked_user.balance -= balance_cost

        asset = uow.assets.add_item_quantity(
            locked_user.id,
            item.id,
            quantity,
        )

        result_data: dict[str, object] = {
            "execution_public_id": str(claim.execution.public_id),
            "request_id": str(request_id),
            "item_public_id": str(item.public_id),
            "purchased_quantity": quantity,
            "total_quantity": asset.quantity,
            "balance": locked_user.balance,
        }

        uow.executions.complete(
            claim.execution,
            balance_cost=balance_cost,
            result_data=result_data,
        )
        uow.commit()

        return result_data
