import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.cat_memory import CatMemoryRead


class CatConversationContextRead(BaseModel):
    cat_asset_public_id: uuid.UUID
    cat_public_id: uuid.UUID
    name: str
    persona: str
    memories: list[CatMemoryRead]


class CatChatCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=240)


class CatChatRead(BaseModel):
    cat_asset_public_id: uuid.UUID
    reply: str
    category: Literal[
        "COMPANION",
        "CODING",
        "UNKNOWN",
        "PROMPT_INJECTION",
        "SAFETY",
        "PROFESSIONAL",
    ]
    memory_count: int
    remembered: bool
