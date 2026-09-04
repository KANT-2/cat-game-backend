from uuid import UUID

from app.core.exceptions import (
    InvalidMemorySummaryError,
    ResourceNotFoundError,
)
from app.core.unit_of_work import UnitOfWork
from app.schemas.cat_conversation import CatConversationContextRead
from app.schemas.cat_memory import (
    CatMemoryRead,
    to_cat_memory_read,
)


def get_cat_conversation_context(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    cat_asset_public_id: UUID,
) -> CatConversationContextRead:
    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")

        cat_asset = uow.assets.get_by_public_id(
            cat_asset_public_id
        )
        if (
            cat_asset is None
            or cat_asset.user_id != user.id
            or cat_asset.cat_id is None
        ):
            raise ResourceNotFoundError("cat asset not found")

        cat = uow.cats.get_by_id(cat_asset.cat_id)
        if cat is None:
            raise ResourceNotFoundError("cat not found")

        memories = uow.cat_memories.list_by_cat_asset_id(
            cat_asset.id
        )

        return CatConversationContextRead(
            cat_asset_public_id=cat_asset.public_id,
            cat_public_id=cat.public_id,
            name=cat.name,
            persona=cat.persona,
            memories=[
                to_cat_memory_read(
                    memory,
                    cat_asset_public_id=cat_asset.public_id,
                )
                for memory in memories
            ],
        )

def add_cat_memory(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    cat_asset_public_id: UUID,
    context_summary: str,
) -> CatMemoryRead:
    if not context_summary.strip():
        raise InvalidMemorySummaryError(
            "context summary must not be blank"
        )
    
    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")

        cat_asset = uow.assets.get_by_public_id(
            cat_asset_public_id
        )
        if (
            cat_asset is None
            or cat_asset.user_id != user.id
            or cat_asset.cat_id is None
        ):
            raise ResourceNotFoundError("cat asset not found")

        memory = uow.cat_memories.add(
            cat_asset.id,
            context_summary,
        )

        uow.commit()

        return to_cat_memory_read(
            memory,
            cat_asset_public_id=cat_asset.public_id,
        )

def delete_cat_memory(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    cat_asset_public_id: UUID,
    memory_public_id: UUID,
) -> None:
    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")

        cat_asset = uow.assets.get_by_public_id(
            cat_asset_public_id
        )
        if (
            cat_asset is None
            or cat_asset.user_id != user.id
            or cat_asset.cat_id is None
        ):
            raise ResourceNotFoundError("cat asset not found")

        memory = (
            uow.cat_memories.get_by_public_id_for_update(
                memory_public_id
            )
        )
        if (
            memory is None
            or memory.cat_asset_id != cat_asset.id
        ):
            raise ResourceNotFoundError("cat memory not found")

        uow.cat_memories.remove(memory)
        uow.commit()

def delete_all_cat_memories(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    cat_asset_public_id: UUID,
) -> None:
    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")

        cat_asset = uow.assets.get_by_public_id(
            cat_asset_public_id
        )
        if (
            cat_asset is None
            or cat_asset.user_id != user.id
            or cat_asset.cat_id is None
        ):
            raise ResourceNotFoundError("cat asset not found")

        uow.cat_memories.remove_all_by_cat_asset_id(
            cat_asset.id
        )
        uow.commit()
