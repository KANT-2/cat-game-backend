import uuid

from pydantic import BaseModel

from app.schemas.base import ReadSchema


class TaskRead(ReadSchema):
    concept_public_id: uuid.UUID
    title: str
    type: str
    domain: str
    difficulty: str
    description: str
    template_code: str
    options: dict[str, str] | None
    hint_text: str | None
    is_active: bool

    # test_cases와 correct_option은 채점 전용 정보라 의도적으로 포함하지 않는다.


class TaskCreate(BaseModel):
    concept_public_id: uuid.UUID
    title: str
    type: str  # "MULTIPLE_CHOICE" 또는 "CODE"
    domain: str
    difficulty: str  # "BRONZE" / "SILVER" / "GOLD"
    description: str
    template_code: str = ""
    options: dict[str, str] | None = None
    hint_text: str | None = None