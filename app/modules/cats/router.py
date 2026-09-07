import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import CurrentUser
from app.core.config import settings
from app.core.exceptions import (
    InvalidMemorySummaryError,
    ResourceNotFoundError,
)
from app.core.unit_of_work import UnitOfWork
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.integrations.ai.cat_chat import (
    CatChatProvider,
    GeminiCatChatProvider,
    RuleBasedCatChatProvider,
)
from app.modules.cats import service as cat_service
from app.schemas.cat_collection import CatCollectionRead
from app.schemas.cat_conversation import CatChatCreate, CatChatRead, CatConversationContextRead
from app.schemas.cat_memory import CatMemoryCreate, CatMemoryRead

router = APIRouter(prefix="/cats", tags=["cats"])


def get_cat_unit_of_work() -> UnitOfWork:
    return SqlAlchemyUnitOfWork()


CatUnitOfWork = Annotated[
    UnitOfWork,
    Depends(get_cat_unit_of_work),
]


@lru_cache(maxsize=1)
def get_cat_chat_provider() -> CatChatProvider:
    api_key = settings.gemini_api_key
    if api_key is not None and api_key.get_secret_value().strip():
        return GeminiCatChatProvider(
            api_key=api_key.get_secret_value(),
            model=settings.gemini_model,
            timeout_ms=int(settings.gemini_timeout_seconds * 1000),
        )
    return RuleBasedCatChatProvider()


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


CatChatProviderDependency = Annotated[
    CatChatProvider,
    Depends(get_cat_chat_provider),
]


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
    response_model=CatChatRead,
)
def create_cat_chat(
    cat_asset_public_id: uuid.UUID,
    payload: CatChatCreate,
    current_user: CurrentUser,
    unit_of_work: CatUnitOfWork,
    provider: CatChatProviderDependency,
) -> CatChatRead:
    try:
        return cat_service.chat_with_cat(
            unit_of_work=unit_of_work,
            provider=provider,
            user_public_id=current_user.public_id,
            cat_asset_public_id=cat_asset_public_id,
            message=payload.message,
            recent_messages=[entry.model_dump() for entry in payload.recent_messages],
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
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
