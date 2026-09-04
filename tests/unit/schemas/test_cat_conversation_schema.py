import uuid
from datetime import UTC, datetime

from app.schemas.cat_conversation import (
    CatConversationContextRead,
)
from app.schemas.cat_memory import CatMemoryRead


def test_cat_conversation_context_exposes_persona_and_memories() -> None:
    cat_asset_public_id = uuid.uuid4()
    cat_public_id = uuid.uuid4()
    memory_public_id = uuid.uuid4()
    created_at = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)

    memory = CatMemoryRead(
        public_id=memory_public_id,
        cat_asset_public_id=cat_asset_public_id,
        context_summary="사용자는 나비에게 파이썬 반복문을 질문했다.",
        created_at=created_at,
    )

    result = CatConversationContextRead(
        cat_asset_public_id=cat_asset_public_id,
        cat_public_id=cat_public_id,
        name="나비",
        persona="친절하고 차분하게 코딩을 설명하는 고양이",
        memories=[memory],
    )

    dumped = result.model_dump()

    assert result.cat_asset_public_id == cat_asset_public_id
    assert result.cat_public_id == cat_public_id
    assert result.name == "나비"
    assert result.persona == "친절하고 차분하게 코딩을 설명하는 고양이"
    assert result.memories == [memory]
    assert "id" not in dumped
    assert "cat_id" not in dumped
    assert "cat_asset_id" not in dumped
