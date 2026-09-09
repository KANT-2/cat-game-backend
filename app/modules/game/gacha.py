"""Idempotent gacha command matching the PWA reward catalog."""

import random
from dataclasses import dataclass
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
from app.modules.game.catalog import ITEM_DEFINITIONS

_OPERATION_TYPE = "GAME_GACHA"
_COSTS = {1: 30, 11: 300}
_DUPLICATE_CAT_COINS = 15


@dataclass(frozen=True, slots=True)
class RewardDefinition:
    catalog_key: str
    kind: str
    weight: float


def _build_rewards() -> tuple[RewardDefinition, ...]:
    # Keep the original category budgets; share each budget across its catalog items.
    groups = (
        (0.10, {"desk", "hideout"}),
        (0.25, {"catTree", "scratcher"}),
        (0.30, {"plant"}),
        (0.30, {"sofa", "bed", "rug", "litterBox"}),
    )
    rewards = [RewardDefinition("ink", "cat", 0.05)]
    for weight, kinds in groups:
        items = [
            item
            for item in ITEM_DEFINITIONS
            if item.category == "FURNITURE" and item.furniture_kind in kinds
        ]
        rewards.extend(
            RewardDefinition(item.catalog_key, "furniture", weight / len(items)) for item in items
        )
    return tuple(rewards)


_REWARDS = _build_rewards()


def draw_game_gacha(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    request_id: UUID,
    draw_count: int,
    random_source: random.Random | random.SystemRandom | None = None,
) -> dict[str, object]:
    """Charge once and persist every reward under an idempotency key.

    @param unit_of_work: Transaction and repositories used for the command.
    @param user_public_id: Authenticated player's public UUID.
    @param request_id: Client-generated UUID reused when retrying the same request.
    @param draw_count: Supported draw size, currently 1 or 11.
    @param random_source: Injectable source used by deterministic tests.
    @returns Persisted reward details and the final balance.
    @throws IdempotencyConflictError: The request UUID was reused with another payload.
    """
    if draw_count not in _COSTS:
        raise InvalidQuantityError("draw_count must be 1 or 11")

    request_payload: dict[str, object] = {"draw_count": draw_count}
    request_hash = build_request_hash(operation_type=_OPERATION_TYPE, payload=request_payload)
    source = random_source or random.SystemRandom()

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
            if claim.execution.result_data is None:
                raise RuntimeError("completed execution has no result data")
            return dict(claim.execution.result_data)

        locked_user = uow.users.get_for_update(user.id)
        if locked_user is None:
            raise ResourceNotFoundError("user not found")
        cost = _COSTS[draw_count]
        if locked_user.balance < cost:
            raise InsufficientBalanceError("insufficient balance")
        locked_user.balance -= cost

        rewards: list[dict[str, object]] = []
        for _ in range(draw_count):
            definition = _draw_reward(source.random())
            if definition.kind == "cat":
                cat = uow.cats.get_by_catalog_key(definition.catalog_key)
                if cat is None:
                    raise ResourceNotFoundError("gacha cat not found")
                duplicate = uow.assets.get_cat_asset(locked_user.id, cat.id) is not None
                exchange_coins = _DUPLICATE_CAT_COINS if duplicate else 0
                if duplicate:
                    locked_user.balance += exchange_coins
                else:
                    uow.assets.grant_cat(locked_user.id, cat.id)
                rewards.append(
                    {
                        "id": f"cat.{definition.catalog_key}",
                        "kind": "cat",
                        "cat_variant": definition.catalog_key,
                        "shop_item_id": None,
                        "duplicate": duplicate,
                        "exchange_coins": exchange_coins,
                    }
                )
                continue

            item = uow.items.get_by_catalog_key(definition.catalog_key)
            if item is None:
                raise ResourceNotFoundError("gacha item not found")
            uow.assets.add_item_quantity(locked_user.id, item.id, 1)
            rewards.append(
                {
                    "id": definition.catalog_key,
                    "kind": "furniture",
                    "cat_variant": None,
                    "shop_item_id": definition.catalog_key,
                    "duplicate": False,
                    "exchange_coins": 0,
                }
            )

        result: dict[str, object] = {
            "request_id": str(request_id),
            "rewards": rewards,
            "remaining_balance": locked_user.balance,
        }
        claim.execution.draw_count = draw_count
        uow.executions.complete(claim.execution, balance_cost=cost, result_data=result)
        locked_user.advance_state_version()
        uow.commit()
        return result


def _draw_reward(value: float) -> RewardDefinition:
    boundary = 0.0
    bounded = min(max(value, 0.0), 0.999_999_999)
    for reward in _REWARDS:
        boundary += reward.weight
        if bounded < boundary:
            return reward
    return _REWARDS[-1]
