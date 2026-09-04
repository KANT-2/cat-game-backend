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
from app.modules.gacha.policy import GachaPolicy

_OPERATION_TYPE = "CAT_GACHA"


def draw_cats(
    *,
    unit_of_work: UnitOfWork,
    policy: GachaPolicy,
    user_public_id: UUID,
    request_id: UUID,
    draw_count: int,
) -> dict[str, object]:
    if draw_count not in {1, 10}:
        raise InvalidQuantityError("draw_count must be 1 or 10")

    request_payload: dict[str, object] = {
        "draw_count": draw_count,
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

        balance_cost = policy.calculate_balance_cost(
            draw_count=draw_count,
        )

        if balance_cost < 0:
            raise RuntimeError("gacha policy returned negative balance cost")

        locked_user = uow.users.get_for_update(user.id)
        if locked_user is None:
            raise ResourceNotFoundError("user not found")

        if locked_user.balance < balance_cost:
            raise InsufficientBalanceError("insufficient balance")

        bonus_draw_count = 1 if draw_count == 10 else 0
        reward_count = draw_count + bonus_draw_count
        rewards = policy.draw(draw_count=reward_count)

        if any(reward.duplicate_mileage < 0 for reward in rewards):
            raise RuntimeError("gacha policy returned negative duplicate mileage")

        if len(rewards) != reward_count:
            raise RuntimeError("gacha policy returned wrong reward count")

        selected = []
        for reward in rewards:
            cat = uow.cats.get_by_public_id(reward.cat_public_id)
            if cat is None:
                raise ResourceNotFoundError("cat not found")
            selected.append((cat, reward))

        locked_user.balance -= balance_cost

        results: list[dict[str, object]] = []
        for cat, reward in selected:
            existing_asset = uow.assets.get_cat_asset(
                locked_user.id,
                cat.id,
            )

            if existing_asset is None:
                uow.assets.grant_cat(locked_user.id, cat.id)
                is_duplicate = False
                mileage_awarded = 0
            else:
                locked_user.mileage += reward.duplicate_mileage
                is_duplicate = True
                mileage_awarded = reward.duplicate_mileage

            results.append(
                {
                    "cat_public_id": str(cat.public_id),
                    "name": cat.name,
                    "rarity": cat.rarity,
                    "is_duplicate": is_duplicate,
                    "mileage_awarded": mileage_awarded,
                }
            )

        result_data: dict[str, object] = {
            "execution_public_id": str(claim.execution.public_id),
            "request_id": str(request_id),
            "draw_count": draw_count,
            "bonus_draw_count": bonus_draw_count,
            "balance_cost": balance_cost,
            "balance": locked_user.balance,
            "mileage": locked_user.mileage,
            "results": results,
        }

        claim.execution.draw_count = draw_count
        uow.executions.complete(
            claim.execution,
            balance_cost=balance_cost,
            result_data=result_data,
        )
        uow.commit()

        return result_data
