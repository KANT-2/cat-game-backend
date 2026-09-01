from datetime import datetime
import uuid
from app.schemas.base import ReadSchema


class CatMemoryRead(ReadSchema):
    user_cat_public_id: uuid.UUID
    context_summary: str
    created_at: datetime