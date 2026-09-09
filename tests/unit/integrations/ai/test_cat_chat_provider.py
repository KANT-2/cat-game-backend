from types import SimpleNamespace
from unittest.mock import MagicMock

from app.integrations.ai.cat_chat import CatReplyPayload, GeminiCatChatProvider


def test_cat_chat_provider_uses_shared_structured_gemini_adapter(monkeypatch) -> None:
    ai_client = MagicMock()
    ai_client.generate_structured.return_value = SimpleNamespace(
        data=CatReplyPayload(reply="좋아, 같이 공놀이하자! 냐옹."),
    )
    client_factory = MagicMock(return_value=ai_client)
    monkeypatch.setattr("app.integrations.ai.cat_chat.GeminiAITextClient", client_factory)
    provider = GeminiCatChatProvider(api_key="test-key", model="gemini-test", timeout_ms=30_000)

    reply = provider.reply(
        persona="활발하고 장난기 많은 고양이",
        message="우리 같이 놀까?",
        memories=[],
        recent_messages=[],
    )

    assert reply == "좋아, 같이 공놀이하자! 냐옹."
    client_factory.assert_called_once_with(
        api_key="test-key",
        model="gemini-test",
        timeout_seconds=30,
    )
    call = ai_client.generate_structured.call_args.kwargs
    assert call["response_schema"] is CatReplyPayload
    assert call["messages"][0].role == "user"
    assert "우리 같이 놀까?" in call["messages"][0].text
