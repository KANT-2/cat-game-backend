import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ResourceNotFoundError
from app.integrations.ai.contracts import AIMessage, AIStructuredResult
from app.models.asset import Asset
from app.models.cat import Cat
from app.models.cat_memory import CatMemory
from app.models.user import User
from app.modules.cats.service import chat_with_cat
from app.schemas.cat_chat import CatChatGeneration
from tests.fakes.repositories import (
    FakeAssetRepository,
    FakeCatMemoryRepository,
    FakeCatRepository,
    FakeUserRepository,
)


def _build_chat_context(
    memories: list[CatMemory] | None = None,
) -> tuple[MagicMock, MagicMock, User, Cat, Asset]:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="chat-owner@example.com",
        username="chat-owner",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    cat = Cat(
        id=2,
        public_id=uuid.uuid4(),
        name="나비",
        persona="장난스럽지만 코딩은 차근차근 설명한다.",
        rarity="COMMON",
    )
    cat_asset = Asset(
        id=3,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=cat.id,
        item_id=None,
        quantity=1,
    )
    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository([cat_asset])
    unit_of_work.cat_memories = FakeCatMemoryRepository(memories)
    ai_client = MagicMock()
    return unit_of_work, ai_client, user, cat, cat_asset


def test_chat_uses_persona_recent_history_and_latest_memories() -> None:
    now = datetime(2026, 9, 5, tzinfo=UTC)
    old_memory = CatMemory(
        id=10,
        public_id=uuid.uuid4(),
        cat_asset_id=3,
        context_summary="오래된 기억",
        created_at=now - timedelta(days=1),
    )
    recent_memory = CatMemory(
        id=11,
        public_id=uuid.uuid4(),
        cat_asset_id=3,
        context_summary="사용자는 반복문을 배우고 있다.",
        created_at=now,
    )
    unit_of_work, ai_client, user, cat, cat_asset = _build_chat_context([old_memory, recent_memory])
    ai_client.generate_structured.return_value = AIStructuredResult(
        data=CatChatGeneration(reply="for문부터 시작하자!", memory_summary=None),
        input_tokens=30,
        output_tokens=8,
    )
    recent_messages = [AIMessage(role="assistant", text="무엇을 공부할까?")]

    result = chat_with_cat(
        unit_of_work=unit_of_work,
        ai_client=ai_client,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset.public_id,
        message="반복문 예제를 보여줘",
        recent_messages=recent_messages,
        max_output_tokens=512,
        max_memory_count=1,
    )

    call = ai_client.generate_structured.call_args.kwargs
    assert cat.name in call["system_instruction"]
    assert cat.persona in call["system_instruction"]
    assert recent_memory.context_summary in call["system_instruction"]
    assert old_memory.context_summary not in call["system_instruction"]
    assert call["messages"] == [
        *recent_messages,
        AIMessage(role="user", text="반복문 예제를 보여줘"),
    ]
    assert call["max_output_tokens"] == 512
    assert call["response_schema"] is CatChatGeneration
    assert result.reply == "for문부터 시작하자!"
    assert result.input_tokens == 30
    assert result.output_tokens == 8
    assert result.memory is None
    unit_of_work.commit.assert_not_called()


def test_chat_appends_new_durable_memory() -> None:
    unit_of_work, ai_client, user, _, cat_asset = _build_chat_context()
    ai_client.generate_structured.return_value = AIStructuredResult(
        data=CatChatGeneration(
            reply="예제 중심으로 설명할게!",
            memory_summary="사용자는 예제 중심의 설명을 선호한다.",
        ),
        input_tokens=25,
        output_tokens=10,
    )

    result = chat_with_cat(
        unit_of_work=unit_of_work,
        ai_client=ai_client,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset.public_id,
        message="예제로 설명해 줘",
        recent_messages=[],
        max_output_tokens=512,
        max_memory_count=20,
    )

    assert result.memory is not None
    assert result.memory.cat_asset_public_id == cat_asset.public_id
    assert result.memory.context_summary == "사용자는 예제 중심의 설명을 선호한다."
    assert len(unit_of_work.cat_memories.memories) == 1
    unit_of_work.commit.assert_called_once_with()


def test_chat_does_not_store_exact_duplicate_memory() -> None:
    existing = CatMemory(
        id=10,
        public_id=uuid.uuid4(),
        cat_asset_id=3,
        context_summary="사용자는 파이썬을 공부하고 있다.",
        created_at=datetime(2026, 9, 5, tzinfo=UTC),
    )
    unit_of_work, ai_client, user, _, cat_asset = _build_chat_context([existing])
    ai_client.generate_structured.return_value = AIStructuredResult(
        data=CatChatGeneration(
            reply="기억하고 있어!",
            memory_summary=existing.context_summary,
        )
    )

    result = chat_with_cat(
        unit_of_work=unit_of_work,
        ai_client=ai_client,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset.public_id,
        message="내가 뭘 공부했지?",
        recent_messages=[],
        max_output_tokens=512,
        max_memory_count=20,
    )

    assert result.memory is None
    assert unit_of_work.cat_memories.memories == [existing]
    unit_of_work.commit.assert_not_called()


def test_chat_checks_cat_ownership_before_calling_ai() -> None:
    unit_of_work, ai_client, user, _, cat_asset = _build_chat_context()
    cat_asset.user_id = 999

    with pytest.raises(ResourceNotFoundError, match="cat asset not found"):
        chat_with_cat(
            unit_of_work=unit_of_work,
            ai_client=ai_client,
            user_public_id=user.public_id,
            cat_asset_public_id=cat_asset.public_id,
            message="안녕",
            recent_messages=[],
            max_output_tokens=512,
            max_memory_count=20,
        )

    ai_client.generate_structured.assert_not_called()
