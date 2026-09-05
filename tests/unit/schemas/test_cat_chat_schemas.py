import uuid

import pytest
from pydantic import ValidationError

from app.schemas.cat_chat import (
    CatChatGeneration,
    CatChatMessage,
    CatChatRequest,
    CatChatResponse,
)


def test_cat_chat_request_strips_messages_and_rejects_extra_fields() -> None:
    request = CatChatRequest(
        message="  반복문을 알려줘  ",
        recent_messages=[CatChatMessage(role="assistant", text="  무엇을 도와줄까?  ")],
    )

    assert request.message == "반복문을 알려줘"
    assert request.recent_messages[0].text == "무엇을 도와줄까?"

    with pytest.raises(ValidationError):
        CatChatRequest.model_validate(
            {
                "message": "안녕",
                "recent_messages": [],
                "internal_id": 1,
            }
        )


def test_cat_chat_request_limits_recent_history_and_rejects_blank_text() -> None:
    with pytest.raises(ValidationError):
        CatChatRequest(
            message="안녕",
            recent_messages=[CatChatMessage(role="user", text=str(index)) for index in range(11)],
        )

    with pytest.raises(ValidationError):
        CatChatRequest(message="   ")


def test_cat_chat_generation_normalizes_optional_memory() -> None:
    generated = CatChatGeneration(
        reply="  같이 연습해 보자!  ",
        memory_summary="   ",
    )

    assert generated.reply == "같이 연습해 보자!"
    assert generated.memory_summary is None


def test_cat_chat_response_does_not_expose_internal_ids() -> None:
    response = CatChatResponse(
        cat_asset_public_id=uuid.uuid4(),
        reply="야옹!",
        input_tokens=10,
        output_tokens=4,
    )

    dumped = response.model_dump()

    assert set(dumped) == {
        "cat_asset_public_id",
        "reply",
        "memory",
        "input_tokens",
        "output_tokens",
    }
    assert "id" not in dumped
    assert "cat_asset_id" not in dumped
