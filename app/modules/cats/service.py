from uuid import UUID

from app.core.exceptions import (
    InvalidMemorySummaryError,
    ResourceNotFoundError,
)
from app.core.unit_of_work import UnitOfWork
from app.integrations.ai.cat_chat import CatChatProvider
from app.modules.cats.chat_policy import (
    cat_chat_memory_summary,
    classify_cat_chat,
    safe_cat_chat_output,
)
from app.schemas.cat_collection import (
    CatCollectionItemRead,
    CatCollectionRead,
)
from app.schemas.cat_conversation import CatChatRead, CatConversationContextRead
from app.schemas.cat_memory import (
    CatMemoryRead,
    to_cat_memory_read,
)


def get_cat_collection(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
) -> CatCollectionRead:
    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")

        cats = uow.cats.list_all()
        owned_assets = {
            asset.cat_id: asset for asset in uow.assets.list_cat_assets_by_user_id(user.id)
        }

        collection = []
        for cat in cats:
            asset = owned_assets.get(cat.id)
            collection.append(
                CatCollectionItemRead(
                    cat_public_id=cat.public_id,
                    cat_asset_public_id=(asset.public_id if asset is not None else None),
                    name=cat.name,
                    persona=cat.persona,
                    rarity=cat.rarity,
                    is_owned=asset is not None,
                )
            )

        return CatCollectionRead(
            total_count=len(collection),
            owned_count=sum(cat.is_owned for cat in collection),
            cats=collection,
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

        cat_asset = uow.assets.get_by_public_id(cat_asset_public_id)
        if cat_asset is None or cat_asset.user_id != user.id or cat_asset.cat_id is None:
            raise ResourceNotFoundError("cat asset not found")

        cat = uow.cats.get_by_id(cat_asset.cat_id)
        if cat is None:
            raise ResourceNotFoundError("cat not found")

        memories = uow.cat_memories.list_by_cat_asset_id(cat_asset.id)

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


def chat_with_cat(
    *,
    unit_of_work: UnitOfWork,
    provider: CatChatProvider,
    user_public_id: UUID,
    cat_asset_public_id: UUID,
    message: str,
    recent_messages: list[dict[str, str]] | None = None,
) -> CatChatRead:
    """Reply as an owned cat without storing raw user input.

    Prompt-control, unsafe, and professional input is answered before the provider boundary.
    Other safe input reaches the provider, while only coding and companion categories are remembered.
    """
    decision = classify_cat_chat(message)
    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")
        cat_asset = uow.assets.get_by_public_id(cat_asset_public_id)
        if cat_asset is None or cat_asset.user_id != user.id or cat_asset.cat_id is None:
            raise ResourceNotFoundError("cat asset not found")
        cat = uow.cats.get_by_id(cat_asset.cat_id)
        if cat is None:
            raise ResourceNotFoundError("cat not found")
        memories = uow.cat_memories.list_by_cat_asset_id(cat_asset.id)
        persona = cat.persona
        memory_summaries = [memory.context_summary for memory in memories[-6:]]
        memory_count = len(memories)

    if decision.direct_reply is not None:
        return CatChatRead(
            cat_asset_public_id=cat_asset_public_id,
            reply=decision.direct_reply,
            category=decision.category,
            memory_count=memory_count,
            remembered=False,
        )

    try:
        reply = safe_cat_chat_output(
            provider.reply(
                persona=persona,
                message=decision.message,
                memories=memory_summaries,
                recent_messages=(recent_messages or [])[-10:],
            )
        )
    except Exception:  # noqa: BLE001 - provider failures must not escape into the game response
        reply = None
    if reply is None:
        return CatChatRead(
            cat_asset_public_id=cat_asset_public_id,
            reply="냐아… 잠깐 졸았나 봐. 한 번만 다시 말해 줄래?",
            category=decision.category,
            memory_count=memory_count,
            remembered=False,
        )

    if not decision.remember:
        return CatChatRead(
            cat_asset_public_id=cat_asset_public_id,
            reply=reply,
            category=decision.category,
            memory_count=memory_count,
            remembered=False,
        )

    summary = cat_chat_memory_summary(decision.category)
    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")
        locked_user = uow.users.get_for_update(user.id)
        if locked_user is None:
            raise ResourceNotFoundError("user not found")
        cat_asset = uow.assets.get_by_public_id(cat_asset_public_id)
        if cat_asset is None or cat_asset.user_id != user.id or cat_asset.cat_id is None:
            raise ResourceNotFoundError("cat asset not found")
        uow.cat_memories.add(cat_asset.id, summary)
        locked_user.advance_state_version()
        uow.commit()
        memory_count = len(uow.cat_memories.list_by_cat_asset_id(cat_asset.id))

    return CatChatRead(
        cat_asset_public_id=cat_asset_public_id,
        reply=reply,
        category=decision.category,
        memory_count=memory_count,
        remembered=True,
    )


def add_cat_memory(
    *,
    unit_of_work: UnitOfWork,
    user_public_id: UUID,
    cat_asset_public_id: UUID,
    context_summary: str,
) -> CatMemoryRead:
    if not context_summary.strip():
        raise InvalidMemorySummaryError("context summary must not be blank")

    with unit_of_work as uow:
        user = uow.users.get_by_public_id(user_public_id)
        if user is None:
            raise ResourceNotFoundError("user not found")
        locked_user = uow.users.get_for_update(user.id)
        if locked_user is None:
            raise ResourceNotFoundError("user not found")

        cat_asset = uow.assets.get_by_public_id(cat_asset_public_id)
        if cat_asset is None or cat_asset.user_id != user.id or cat_asset.cat_id is None:
            raise ResourceNotFoundError("cat asset not found")

        memory = uow.cat_memories.add(
            cat_asset.id,
            context_summary,
        )

        locked_user.advance_state_version()
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
        locked_user = uow.users.get_for_update(user.id)
        if locked_user is None:
            raise ResourceNotFoundError("user not found")

        cat_asset = uow.assets.get_by_public_id(cat_asset_public_id)
        if cat_asset is None or cat_asset.user_id != user.id or cat_asset.cat_id is None:
            raise ResourceNotFoundError("cat asset not found")

        memory = uow.cat_memories.get_by_public_id_for_update(memory_public_id)
        if memory is None or memory.cat_asset_id != cat_asset.id:
            raise ResourceNotFoundError("cat memory not found")

        uow.cat_memories.remove(memory)
        locked_user.advance_state_version()
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
        locked_user = uow.users.get_for_update(user.id)
        if locked_user is None:
            raise ResourceNotFoundError("user not found")

        cat_asset = uow.assets.get_by_public_id(cat_asset_public_id)
        if cat_asset is None or cat_asset.user_id != user.id or cat_asset.cat_id is None:
            raise ResourceNotFoundError("cat asset not found")

        uow.cat_memories.remove_all_by_cat_asset_id(cat_asset.id)
        locked_user.advance_state_version()
        uow.commit()
