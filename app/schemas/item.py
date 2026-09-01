from app.schemas.base import ReadSchema


class ItemRead(ReadSchema):
    category: str
    name: str
    price: int
