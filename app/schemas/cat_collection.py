import uuid

from pydantic import BaseModel, Field


class CatCollectionItemRead(BaseModel):
    cat_public_id: uuid.UUID
    cat_asset_public_id: uuid.UUID | None
    name: str
    persona: str
    rarity: str
    is_owned: bool


class CatCollectionRead(BaseModel):
    total_count: int = Field(ge=0)
    owned_count: int = Field(ge=0)
    cats: list[CatCollectionItemRead]
