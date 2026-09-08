from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GachaReward:
    cat_public_id: UUID
    duplicate_mileage: int


class GachaPolicy(Protocol):
    def calculate_balance_cost(
        self,
        *,
        draw_count: int,
    ) -> int: ...

    def draw(
        self,
        *,
        draw_count: int,
    ) -> Sequence[GachaReward]: ...
