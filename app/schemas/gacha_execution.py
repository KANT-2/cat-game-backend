from datetime import datetime
import uuid
from app.schemas.base import ReadSchema


class GachaExecutionRead(ReadSchema):
    request_id: uuid.UUID
    operation_type: str
    status: str
    draw_count: int | None
    balance_cost: int
    result_data: dict | None
    created_at: datetime
    completed_at: datetime | None