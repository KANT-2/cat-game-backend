import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.cat_memory import CatMemoryRead


class CatChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be blank")
        return stripped


class CatChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    recent_messages: list[CatChatMessage] = Field(default_factory=list, max_length=10)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class CatChatGeneration(BaseModel):
    reply: str = Field(min_length=1, max_length=2000)
    memory_summary: str | None = Field(default=None, max_length=500)

    @field_validator("reply")
    @classmethod
    def reply_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reply must not be blank")
        return stripped

    @field_validator("memory_summary")
    @classmethod
    def normalize_memory_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CatChatResponse(BaseModel):
    cat_asset_public_id: uuid.UUID
    reply: str
    memory: CatMemoryRead | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
