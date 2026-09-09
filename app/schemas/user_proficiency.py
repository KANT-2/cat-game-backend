import uuid
from typing import Literal

from pydantic import BaseModel


class UserProficiencyRead(BaseModel):
    concept_public_id: uuid.UUID
    proficiency_level: int


class ConceptProficiencyRead(UserProficiencyRead):
    domain: Literal["PYTHON", "SQL"]
    name: str
    attempts: int


class WeakConceptRead(ConceptProficiencyRead):
    pass
