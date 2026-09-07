from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.genai import errors
from pydantic import BaseModel

from app.core.exceptions import (
    AIProviderUnavailableError,
    InvalidAIResponseError,
)
from app.integrations.ai.contracts import AIMessage
from app.integrations.ai.gemini import GeminiAITextClient


class _ChatOutput(BaseModel):
    reply: str
    memory_summary: str | None


def _build_client(monkeypatch):
    sdk_client = MagicMock()
    client_factory = MagicMock(return_value=sdk_client)
    monkeypatch.setattr("app.integrations.ai.gemini.genai.Client", client_factory)

    client = GeminiAITextClient(
        api_key="test-key",
        model="test-model",
        timeout_seconds=30,
    )
    return client, sdk_client


def test_generate_text_maps_messages_and_usage(monkeypatch) -> None:
    client, sdk_client = _build_client(monkeypatch)
    sdk_client.models.generate_content.return_value = SimpleNamespace(
        text="  안녕, 집사!  ",
        parsed=None,
        usage_metadata=SimpleNamespace(
            prompt_token_count=12,
            candidates_token_count=5,
        ),
    )

    result = client.generate_text(
        system_instruction="고양이답게 말한다.",
        messages=[
            AIMessage(role="user", text="안녕?"),
            AIMessage(role="assistant", text="야옹!"),
            AIMessage(role="user", text="오늘 뭐 했어?"),
        ],
        max_output_tokens=128,
    )

    call = sdk_client.models.generate_content.call_args
    assert call.kwargs["model"] == "test-model"
    assert [content.role for content in call.kwargs["contents"]] == [
        "user",
        "model",
        "user",
    ]
    assert result.text == "안녕, 집사!"
    assert result.input_tokens == 12
    assert result.output_tokens == 5


def test_generate_structured_returns_validated_model(monkeypatch) -> None:
    client, sdk_client = _build_client(monkeypatch)
    parsed = _ChatOutput(
        reply="반가워, 집사!",
        memory_summary="사용자는 오늘 반복문을 공부했다.",
    )
    sdk_client.models.generate_content.return_value = SimpleNamespace(
        text=parsed.model_dump_json(),
        parsed=parsed,
        usage_metadata=SimpleNamespace(
            prompt_token_count=20,
            candidates_token_count=10,
        ),
    )

    result = client.generate_structured(
        system_instruction="고양이답게 말한다.",
        messages=[AIMessage(role="user", text="반복문을 공부했어.")],
        max_output_tokens=256,
        response_schema=_ChatOutput,
    )

    call = sdk_client.models.generate_content.call_args
    config = call.kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is _ChatOutput
    assert result.data == parsed
    assert result.input_tokens == 20
    assert result.output_tokens == 10


def test_generate_structured_hides_provider_error_details(monkeypatch) -> None:
    client, sdk_client = _build_client(monkeypatch)
    sdk_client.models.generate_content.side_effect = errors.ClientError(
        429,
        {"error": {"message": "free quota exhausted"}},
    )

    with pytest.raises(
        AIProviderUnavailableError,
        match="AI provider is unavailable",
    ):
        client.generate_structured(
            system_instruction="고양이답게 말한다.",
            messages=[AIMessage(role="user", text="안녕")],
            max_output_tokens=256,
            response_schema=_ChatOutput,
        )


def test_generate_structured_rejects_invalid_json(monkeypatch) -> None:
    client, sdk_client = _build_client(monkeypatch)
    sdk_client.models.generate_content.return_value = SimpleNamespace(
        text="not-json",
        parsed=None,
        usage_metadata=None,
    )

    with pytest.raises(
        InvalidAIResponseError,
        match="invalid structured response",
    ):
        client.generate_structured(
            system_instruction="고양이답게 말한다.",
            messages=[AIMessage(role="user", text="안녕")],
            max_output_tokens=256,
            response_schema=_ChatOutput,
        )
