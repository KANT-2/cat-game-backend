import uuid
from datetime import datetime
from typing import Protocol

from app.schemas.base import ReadSchema


class _CatMemoryReadSource(Protocol):
    public_id: uuid.UUID
    context_summary: str
    created_at: datetime


class CatMemoryRead(ReadSchema):
    user_cat_public_id: uuid.UUID
    context_summary: str
    created_at: datetime


def to_cat_memory_read(
    memory: _CatMemoryReadSource,
    *,
    user_cat_public_id: uuid.UUID,
) -> CatMemoryRead:
    return CatMemoryRead(
        public_id=memory.public_id,
        user_cat_public_id=user_cat_public_id,
        context_summary=memory.context_summary,
        created_at=memory.created_at,
    )
