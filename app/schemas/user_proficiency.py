import uuid

from pydantic import BaseModel


class UserProficiencyRead(BaseModel):
    concept_public_id: uuid.UUID
    proficiency_level: int


class WeakConceptRead(UserProficiencyRead):
    name: str
    attempts: int
