from datetime import datetime
from app.schemas.base import ReadSchema


class UserRead(ReadSchema):
    email: str
    username: str
    role: str
    balance: int
    mileage: int
    house_level: int
    created_at: datetime