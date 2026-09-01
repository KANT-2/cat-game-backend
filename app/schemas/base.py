import uuid
from pydantic import BaseModel, ConfigDict


class ReadSchema(BaseModel):
    """모든 응답 스키마의 기반 클래스.

    내부 INTEGER id는 필드로 선언하지 않는다.
    API로 나가는 값은 항상 public_id(UUID)뿐이다.
    """
    model_config = ConfigDict(from_attributes=True)

    public_id: uuid.UUID