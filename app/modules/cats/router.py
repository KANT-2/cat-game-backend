import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import CurrentUser
from app.core.config import settings
from app.core.exceptions import (
    AIProviderUnavailableError,
    InvalidAIResponseError,
    InvalidMemorySummaryError,
    ResourceNotFoundError,
)
from app.core.unit_of_work import UnitOfWork
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.integrations.ai.contracts import AIMessage, AITextClient
from app.integrations.ai.gemini import GeminiAITextClient
from app.modules.cats import service as cat_service
from app.schemas.cat_chat import CatChatRequest, CatChatResponse
from app.schemas.cat_collection import CatCollectionRead
from app.schemas.cat_conversation import CatConversationContextRead
from app.schemas.cat_memory import CatMemoryCreate, CatMemoryRead

router = APIRouter(prefix="/cats", tags=["cats"])


def get_cat_unit_of_work() -> UnitOfWork:
    return SqlAlchemyUnitOfWork()


CatUnitOfWork = Annotated[
    UnitOfWork,
    Depends(get_cat_unit_of_work),
]


@lru_cache
def get_cat_ai_client() -> AITextClient:
    api_key = settings.gemini_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured",
        )

    return GeminiAITextClient(
        api_key=api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
    )


CatAIClient = Annotated[
    AITextClient,
    Depends(get_cat_ai_client),
]


@router.get(
    "/collection",
    response_model=CatCollectionRead,
)
def read_cat_collection(
    current_user: CurrentUser,
    unit_of_work: CatUnitOfWork,
) -> CatCollectionRead:
    try:
        return cat_service.get_cat_collection(
            unit_of_work=unit_of_work,
            user_public_id=current_user.public_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{cat_asset_public_id}/conversation-context",
    response_model=CatConversationContextRead,
)
def read_cat_conversation_context(
    cat_asset_public_id: uuid.UUID,
    current_user: CurrentUser,
    unit_of_work: CatUnitOfWork,
) -> CatConversationContextRead:
    try:
        return cat_service.get_cat_conversation_context(
            unit_of_work=unit_of_work,
            user_public_id=current_user.public_id,
            cat_asset_public_id=cat_asset_public_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{cat_asset_public_id}/chat",
    response_model=CatChatResponse,
)
def create_cat_chat(
    cat_asset_public_id: uuid.UUID,
    payload: CatChatRequest,
    current_user: CurrentUser,
    unit_of_work: CatUnitOfWork,
    ai_client: CatAIClient,
) -> CatChatResponse:
    try:
        return cat_service.chat_with_cat(
            unit_of_work=unit_of_work,
            ai_client=ai_client,
            user_public_id=current_user.public_id,
            cat_asset_public_id=cat_asset_public_id,
            message=payload.message,
            recent_messages=[
                AIMessage(role=item.role, text=item.text) for item in payload.recent_messages
            ],
            max_output_tokens=settings.gemini_max_output_tokens,
            max_memory_count=settings.gemini_max_memory_count,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (AIProviderUnavailableError, InvalidAIResponseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is temporarily unavailable",
        ) from exc


@router.delete(
    "/{cat_asset_public_id}/memories/{memory_public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_cat_memory(
    cat_asset_public_id: uuid.UUID,
    memory_public_id: uuid.UUID,
    current_user: CurrentUser,
    unit_of_work: CatUnitOfWork,
) -> None:
    try:
        cat_service.delete_cat_memory(
            unit_of_work=unit_of_work,
            user_public_id=current_user.public_id,
            cat_asset_public_id=cat_asset_public_id,
            memory_public_id=memory_public_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{cat_asset_public_id}/memories",
    response_model=CatMemoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_cat_memory(
    cat_asset_public_id: uuid.UUID,
    payload: CatMemoryCreate,
    current_user: CurrentUser,
    unit_of_work: CatUnitOfWork,
) -> CatMemoryRead:
    try:
        return cat_service.add_cat_memory(
            unit_of_work=unit_of_work,
            user_public_id=current_user.public_id,
            cat_asset_public_id=cat_asset_public_id,
            context_summary=payload.context_summary,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidMemorySummaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{cat_asset_public_id}/memories",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_all_cat_memories(
    cat_asset_public_id: uuid.UUID,
    current_user: CurrentUser,
    unit_of_work: CatUnitOfWork,
) -> None:
    try:
        cat_service.delete_all_cat_memories(
            unit_of_work=unit_of_work,
            user_public_id=current_user.public_id,
            cat_asset_public_id=cat_asset_public_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
