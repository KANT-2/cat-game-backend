import uuid

from pydantic import BaseModel

from app.schemas.cat_memory import CatMemoryRead


class CatConversationContextRead(BaseModel):
    cat_asset_public_id: uuid.UUID
    cat_public_id: uuid.UUID
    name: str
    persona: str
    memories: list[CatMemoryRead]