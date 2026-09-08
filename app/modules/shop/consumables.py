from uuid import UUID

from app.core.exceptions import (
    IdempotencyConflictError,
    InvalidItemCategoryError,
    ResourceNotFoundError,
)
from app.core.repository_contracts import ClaimStatus
from app.core.request_hash import build_request_hash
from app.core.unit_of_work import UnitOfWork
from app.modules.game.catalog import ITEM_BY_KEY

_OPERATION_TYPE = "ITEM_CONSUMPTION"


def use_consumable(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    request_id: UUID,
    item_public_id: UUID,
    cat_public_id: UUID,
) -> dict[str, object]:
    """Consume one owned positive-care item exactly once.

    Args:
        unit_of_work: Repository and transaction boundary for the complete command.
        user_public_id: Authenticated player's public UUID.
        request_id: Client-generated idempotency UUID reused only for the same command.
        item_public_id: Consumable catalog item's public UUID.
        cat_public_id: Owned cat catalog entry receiving the care interaction.

    Returns:
        Public IDs, the presentation effect, and remaining item quantity.

    Raises:
        ResourceNotFoundError: User, item, owned item, cat, or owned cat is missing.
        InvalidItemCategoryError: The requested item is not a consumable.
        IdempotencyConflictError: The request UUID was reused with different input.

    Notes:
        The item decrement, execution result, and state version advance commit together.
        This command does not create hunger, decay, or a negative care state.
    """
    request_payload: dict[str, object] = {
        "item_public_id": str(item_public_id),
        "cat_public_id": str(cat_public_id),
    }
    request_hash = build_request_hash(operation_type=_OPERATION_TYPE, payload=request_payload)

    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")
        locked_user = uow.users.get_for_update(user.id)
        if locked_user is None:
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
            if claim.execution.result_data is None:
                raise RuntimeError("completed execution has no result data")
            return dict(claim.execution.result_data)

        item = uow.items.get_by_public_id(item_public_id)
        if item is None:
            raise ResourceNotFoundError("item not found")
        definition = ITEM_BY_KEY.get(item.catalog_key)
        if item.category != "CONSUMABLE" or definition is None or definition.consumable_effect is None:
            raise InvalidItemCategoryError("item is not consumable")
        cat = uow.cats.get_by_public_id(cat_public_id)
        if cat is None or uow.assets.get_cat_asset(locked_user.id, cat.id) is None:
            raise ResourceNotFoundError("owned cat not found")
        remaining_quantity = uow.assets.consume_item_quantity_for_update(locked_user.id, item.id)
        if remaining_quantity is None:
            raise ResourceNotFoundError("owned consumable not found")

        result_data: dict[str, object] = {
            "execution_public_id": str(claim.execution.public_id),
            "request_id": str(request_id),
            "item_public_id": str(item.public_id),
            "cat_public_id": str(cat.public_id),
            "effect": definition.consumable_effect,
            "remaining_quantity": remaining_quantity,
        }
        uow.executions.complete(claim.execution, balance_cost=0, result_data=result_data)
        locked_user.advance_state_version()
        uow.commit()
        return result_data
