from app.schemas.base import ReadSchema


class CatRead(ReadSchema):
    catalog_key: str
    name: str
    persona: str
    rarity: str
