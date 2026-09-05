from collections.abc import Sequence

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.core.exceptions import (
    AIProviderUnavailableError,
    InvalidAIResponseError,
)
from app.integrations.ai.contracts import (
    AIMessage,
    AIStructuredResult,
    AITextClient,
    AITextResult,
)


class GeminiAITextClient(AITextClient):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self._model = model
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_seconds * 1000),
            ),
        )

    def generate_text(
        self,
        *,
        system_instruction: str,
        messages: Sequence[AIMessage],
        max_output_tokens: int,
    ) -> AITextResult:
        contents = [
            types.Content(
                role="model" if message.role == "assistant" else "user",
                parts=[types.Part.from_text(text=message.text)],
            )
            for message in messages
        ]

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_level="minimal"),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True,
                    ),
                ),
            )
        except errors.APIError as exc:
            raise AIProviderUnavailableError("AI provider is unavailable") from exc

        text = response.text
        if text is None or not text.strip():
            raise InvalidAIResponseError("AI provider returned an empty response")

        usage = response.usage_metadata

        return AITextResult(
            text=text.strip(),
            input_tokens=(usage.prompt_token_count if usage is not None else None),
            output_tokens=(usage.candidates_token_count if usage is not None else None),
        )

    def generate_structured[SchemaT: BaseModel](
        self,
        *,
        system_instruction: str,
        messages: Sequence[AIMessage],
        max_output_tokens: int,
        response_schema: type[SchemaT],
    ) -> AIStructuredResult[SchemaT]:
        contents = [
            types.Content(
                role="model" if message.role == "assistant" else "user",
                parts=[types.Part.from_text(text=message.text)],
            )
            for message in messages
        ]

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_level="minimal"),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True,
                    ),
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )
        except errors.APIError as exc:
            raise AIProviderUnavailableError("AI provider is unavailable") from exc

        parsed = response.parsed
        if isinstance(parsed, response_schema):
            data = parsed
        else:
            text = response.text
            if text is None or not text.strip():
                raise InvalidAIResponseError("AI provider returned an empty structured response")
            try:
                data = response_schema.model_validate_json(text)
            except ValidationError as exc:
                raise InvalidAIResponseError(
                    "AI provider returned an invalid structured response"
                ) from exc

        usage = response.usage_metadata

        return AIStructuredResult(
            data=data,
            input_tokens=(usage.prompt_token_count if usage is not None else None),
            output_tokens=(usage.candidates_token_count if usage is not None else None),
        )
