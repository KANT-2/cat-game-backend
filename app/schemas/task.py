import uuid

from app.schemas.base import ReadSchema


class TaskRead(ReadSchema):
    concept_public_id: uuid.UUID
    concept_name: str
    title: str
    type: str
    domain: str
    difficulty: str
    description: str
    template_code: str
    options: dict[str, str] | None
    hint_text: str | None
    is_active: bool
    completed: bool

    # test_cases와 correct_option은 채점 전용 정보라 의도적으로 포함하지 않는다.
