from app.schemas.base import ReadSchema


class CatRead(ReadSchema):
    name: str
    persona: str
    rarity: str