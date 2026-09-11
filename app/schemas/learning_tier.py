import uuid
from typing import Literal

from pydantic import BaseModel


class ConceptTierProgressRead(BaseModel):
    concept_public_id: uuid.UUID
    name: str
    completed: int
    total: int
    required: int
    is_met: bool


class LearningTierRead(BaseModel):
    domain: Literal["PYTHON", "SQL"]
    current_tier: Literal["BRONZE", "SILVER", "GOLD"]
    unlocked_difficulties: list[Literal["BRONZE", "SILVER", "GOLD"]]
    next_tier: Literal["SILVER", "GOLD"] | None
    completed: int
    total: int
    required: int
    concept_required_percent: int
    concepts: list[ConceptTierProgressRead]
