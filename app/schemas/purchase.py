import uuid

from pydantic import BaseModel, ConfigDict, Field


class PurchaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: uuid.UUID
    item_public_id: uuid.UUID
    quantity: int = Field(gt=0)


class PurchaseResponse(BaseModel):
    execution_public_id: uuid.UUID
    request_id: uuid.UUID
    item_public_id: uuid.UUID
    purchased_quantity: int = Field(gt=0)
    total_quantity: int = Field(gt=0)
    balance: int = Field(ge=0)
