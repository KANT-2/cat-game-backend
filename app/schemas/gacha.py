import uuid

from pydantic import BaseModel, ConfigDict, Field


class GachaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    draw_count: int = Field(gt=0)


class GachaDrawResult(BaseModel):
    cat_public_id: uuid.UUID
    name: str
    rarity: str
    is_duplicate: bool
    mileage_awarded: int = Field(ge=0)


class GachaResponse(BaseModel):
    execution_public_id: uuid.UUID
    request_id: uuid.UUID
    draw_count: int = Field(gt=0)
    balance_cost: int = Field(ge=0)
    balance: int = Field(ge=0)
    mileage: int = Field(ge=0)
    results: list[GachaDrawResult]
