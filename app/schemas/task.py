import uuid
from app.schemas.base import ReadSchema


class TaskRead(ReadSchema):
    concept_public_id: uuid.UUID
    title: str
    type: str
    difficulty: str
    description: str
    template_code: str
    hint_text: str | None
    is_active: bool

    # 주의: test_cases는 PRD 요구사항상 비공개 정보이므로
    # 이 응답 스키마에 의도적으로 포함하지 않는다.