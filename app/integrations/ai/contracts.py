from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel

MessageRole = Literal["user", "assistant"]


@dataclass(frozen=True, slots=True)
class AIMessage:
    role: MessageRole
    text: str


@dataclass(frozen=True, slots=True)
class AITextResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class AIStructuredResult[SchemaT: BaseModel]:
    data: SchemaT
    input_tokens: int | None = None
    output_tokens: int | None = None


class AITextClient(Protocol):
    def generate_text(
        self,
        *,
        system_instruction: str,
        messages: Sequence[AIMessage],
        max_output_tokens: int,
    ) -> AITextResult: ...

    def generate_structured[SchemaT: BaseModel](
        self,
        *,
        system_instruction: str,
        messages: Sequence[AIMessage],
        max_output_tokens: int,
        response_schema: type[SchemaT],
    ) -> AIStructuredResult[SchemaT]: ...
