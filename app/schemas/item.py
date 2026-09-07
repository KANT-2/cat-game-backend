from app.schemas.base import ReadSchema


class ItemRead(ReadSchema):
    catalog_key: str
    category: str
    name: str
    price: int
