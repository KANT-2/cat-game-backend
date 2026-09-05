import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.integrations.ai.contracts import AIStructuredResult
from app.main import app
from app.models.asset import Asset
from app.models.cat import Cat
from app.models.cat_memory import CatMemory
from app.models.gacha_execution import GachaExecution
from app.models.item import Item
from app.models.placed_object import PlacedObject
from app.models.user import User
from app.modules.cats.router import get_cat_ai_client
from app.schemas.cat_chat import CatChatGeneration


def test_purchase_http_request_uses_postgresql_and_is_idempotent(
    engine,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "test")

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    user = User(
        email=f"http-purchase-{uuid.uuid4()}@example.com",
        username=f"http-purchase-user-{uuid.uuid4()}",
        balance=1000,
    )
    item = Item(
        name=f"http-purchase-item-{uuid.uuid4()}",
        category="FURNITURE",
        price=300,
    )

    with session_factory() as seed_session:
        seed_session.add_all([user, item])
        seed_session.commit()

    user_id = user.id
    item_id = item.id
    user_public_id = user.public_id
    item_public_id = item.public_id
    request_id = uuid.uuid4()

    request_body = {
        "request_id": str(request_id),
        "item_public_id": str(item_public_id),
        "quantity": 1,
    }
    headers = {
        "X-User-Public-ID": str(user_public_id),
    }

    try:
        with TestClient(app) as client:
            first_response = client.post(
                "/api/v1/shop/purchases",
                json=request_body,
                headers=headers,
            )
            retry_response = client.post(
                "/api/v1/shop/purchases",
                json=request_body,
                headers=headers,
            )

        assert first_response.status_code == 201
        assert retry_response.status_code == 201

        first_payload = first_response.json()
        retry_payload = retry_response.json()

        assert first_payload == retry_payload
        assert first_payload["request_id"] == str(request_id)
        assert first_payload["item_public_id"] == str(item_public_id)
        assert first_payload["purchased_quantity"] == 1
        assert first_payload["total_quantity"] == 1
        assert first_payload["balance"] == 700
        assert set(first_payload) == {
            "execution_public_id",
            "request_id",
            "item_public_id",
            "purchased_quantity",
            "total_quantity",
            "balance",
        }

        with session_factory() as verification_session:
            persisted_user = verification_session.get(User, user_id)
            asset = verification_session.scalar(
                select(Asset).where(
                    Asset.user_id == user_id,
                    Asset.item_id == item_id,
                )
            )
            executions = verification_session.scalars(
                select(GachaExecution).where(GachaExecution.request_id == request_id)
            ).all()

            assert persisted_user is not None
            assert persisted_user.balance == 700
            assert asset is not None
            assert asset.quantity == 1
            assert len(executions) == 1
            assert executions[0].status == "COMPLETED"
    finally:
        with session_factory() as cleanup_session:
            cleanup_session.execute(
                delete(GachaExecution).where(GachaExecution.request_id == request_id)
            )
            cleanup_session.execute(delete(Asset).where(Asset.user_id == user_id))
            cleanup_session.execute(delete(User).where(User.id == user_id))
            cleanup_session.execute(delete(Item).where(Item.id == item_id))
            cleanup_session.commit()


def test_gacha_http_returns_503_without_database_changes(
    engine,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "test")

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    user = User(
        email=f"http-gacha-{uuid.uuid4()}@example.com",
        username=f"http-gacha-user-{uuid.uuid4()}",
        balance=1000,
    )

    with session_factory() as seed_session:
        seed_session.add(user)
        seed_session.commit()

    user_id = user.id
    user_public_id = user.public_id
    request_id = uuid.uuid4()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/gacha/draws",
                json={
                    "request_id": str(request_id),
                    "draw_count": 1,
                },
                headers={
                    "X-User-Public-ID": str(user_public_id),
                },
            )

        assert response.status_code == 503
        assert response.json() == {"detail": "Gacha policy is not configured"}

        with session_factory() as verification_session:
            persisted_user = verification_session.get(User, user_id)
            asset = verification_session.scalar(select(Asset).where(Asset.user_id == user_id))
            execution = verification_session.scalar(
                select(GachaExecution).where(GachaExecution.request_id == request_id)
            )

            assert persisted_user is not None
            assert persisted_user.balance == 1000
            assert persisted_user.mileage == 0
            assert asset is None
            assert execution is None
    finally:
        with session_factory() as cleanup_session:
            cleanup_session.execute(
                delete(GachaExecution).where(GachaExecution.request_id == request_id)
            )
            cleanup_session.execute(delete(Asset).where(Asset.user_id == user_id))
            cleanup_session.execute(delete(User).where(User.id == user_id))
            cleanup_session.commit()


def test_furniture_http_place_update_and_remove_flow(
    engine,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "test")

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    user = User(
        email=f"http-housing-{uuid.uuid4()}@example.com",
        username=f"http-housing-user-{uuid.uuid4()}",
        balance=0,
    )
    item = Item(
        name=f"http-furniture-{uuid.uuid4()}",
        category="FURNITURE",
        price=300,
    )

    with session_factory() as seed_session:
        seed_session.add_all([user, item])
        seed_session.flush()

        asset = Asset(
            user_id=user.id,
            item_id=item.id,
            quantity=1,
        )
        seed_session.add(asset)
        seed_session.commit()

    user_id = user.id
    item_id = item.id
    user_public_id = user.public_id
    item_public_id = item.public_id
    headers = {
        "X-User-Public-ID": str(user_public_id),
    }
    placed_object_public_id = None

    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/api/v1/housing/placed-objects",
                json={
                    "item_public_id": str(item_public_id),
                    "position_data": {
                        "x": 10,
                        "y": 20,
                        "z": 30,
                    },
                },
                headers=headers,
            )

            assert create_response.status_code == 201
            create_payload = create_response.json()
            placed_object_public_id = create_payload["public_id"]

            assert create_payload == {
                "public_id": placed_object_public_id,
                "item_public_id": str(item_public_id),
                "position_data": {
                    "x": 10.0,
                    "y": 20.0,
                    "z": 30.0,
                },
            }
            assert "id" not in create_payload

            update_response = client.patch(
                (f"/api/v1/housing/placed-objects/{placed_object_public_id}"),
                json={
                    "position_data": {
                        "x": 15,
                        "y": 25,
                        "z": 35,
                    }
                },
                headers=headers,
            )

            assert update_response.status_code == 200
            assert update_response.json() == {
                "public_id": placed_object_public_id,
                "item_public_id": str(item_public_id),
                "position_data": {
                    "x": 15.0,
                    "y": 25.0,
                    "z": 35.0,
                },
            }

            delete_response = client.delete(
                (f"/api/v1/housing/placed-objects/{placed_object_public_id}"),
                headers=headers,
            )

            assert delete_response.status_code == 204
            assert delete_response.content == b""

        with session_factory() as verification_session:
            persisted_asset = verification_session.scalar(
                select(Asset).where(
                    Asset.user_id == user_id,
                    Asset.item_id == item_id,
                )
            )
            placed_object = verification_session.scalar(
                select(PlacedObject).where(
                    PlacedObject.public_id == uuid.UUID(placed_object_public_id)
                )
            )

            assert persisted_asset is not None
            assert persisted_asset.quantity == 1
            assert placed_object is None
    finally:
        with session_factory() as cleanup_session:
            if placed_object_public_id is not None:
                cleanup_session.execute(
                    delete(PlacedObject).where(
                        PlacedObject.public_id == uuid.UUID(placed_object_public_id)
                    )
                )
            cleanup_session.execute(delete(Asset).where(Asset.user_id == user_id))
            cleanup_session.execute(delete(User).where(User.id == user_id))
            cleanup_session.execute(delete(Item).where(Item.id == item_id))
            cleanup_session.commit()


def test_wallpaper_and_floor_http_application_flow(
    engine,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "test")

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    user = User(
        email=f"http-surfaces-{uuid.uuid4()}@example.com",
        username=f"http-surfaces-user-{uuid.uuid4()}",
        balance=0,
    )
    wallpaper = Item(
        name=f"http-wallpaper-{uuid.uuid4()}",
        category="WALLPAPER",
        price=100,
    )
    floor = Item(
        name=f"http-floor-{uuid.uuid4()}",
        category="FLOOR",
        price=100,
    )

    with session_factory() as seed_session:
        seed_session.add_all([user, wallpaper, floor])
        seed_session.flush()

        seed_session.add_all(
            [
                Asset(
                    user_id=user.id,
                    item_id=wallpaper.id,
                    quantity=1,
                ),
                Asset(
                    user_id=user.id,
                    item_id=floor.id,
                    quantity=1,
                ),
            ]
        )
        seed_session.commit()

    user_id = user.id
    wallpaper_id = wallpaper.id
    floor_id = floor.id
    user_public_id = user.public_id
    wallpaper_public_id = wallpaper.public_id
    floor_public_id = floor.public_id
    headers = {
        "X-User-Public-ID": str(user_public_id),
    }

    try:
        with TestClient(app) as client:
            wallpaper_response = client.put(
                f"/api/v1/housing/surfaces/{wallpaper_public_id}",
                headers=headers,
            )
            floor_response = client.put(
                f"/api/v1/housing/surfaces/{floor_public_id}",
                headers=headers,
            )

        assert wallpaper_response.status_code == 200
        assert wallpaper_response.json() == {
            "user_public_id": str(user_public_id),
            "item_public_id": str(wallpaper_public_id),
            "category": "WALLPAPER",
        }

        assert floor_response.status_code == 200
        assert floor_response.json() == {
            "user_public_id": str(user_public_id),
            "item_public_id": str(floor_public_id),
            "category": "FLOOR",
        }

        assert "id" not in wallpaper_response.json()
        assert "id" not in floor_response.json()

        with session_factory() as verification_session:
            persisted_user = verification_session.get(User, user_id)

            assert persisted_user is not None
            assert persisted_user.wallpaper_item_id == wallpaper_id
            assert persisted_user.floor_item_id == floor_id
    finally:
        with session_factory() as cleanup_session:
            cleanup_user = cleanup_session.get(User, user_id)
            if cleanup_user is not None:
                cleanup_user.wallpaper_item_id = None
                cleanup_user.floor_item_id = None
                cleanup_session.flush()

            cleanup_session.execute(delete(Asset).where(Asset.user_id == user_id))
            cleanup_session.execute(delete(User).where(User.id == user_id))
            cleanup_session.execute(delete(Item).where(Item.id.in_([wallpaper_id, floor_id])))
            cleanup_session.commit()


def test_cat_collection_context_and_memory_http_flow(
    engine,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "test")

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    user = User(
        email=f"http-cats-{uuid.uuid4()}@example.com",
        username=f"http-cats-user-{uuid.uuid4()}",
        balance=0,
    )
    owned_cat = Cat(
        name=f"owned-cat-{uuid.uuid4()}",
        persona="Calm and friendly",
        rarity="COMMON",
    )
    unowned_cat = Cat(
        name=f"unowned-cat-{uuid.uuid4()}",
        persona="Curious and playful",
        rarity="RARE",
    )

    with session_factory() as seed_session:
        seed_session.add_all([user, owned_cat, unowned_cat])
        seed_session.flush()

        cat_asset = Asset(
            user_id=user.id,
            cat_id=owned_cat.id,
            quantity=1,
        )
        seed_session.add(cat_asset)
        seed_session.commit()

    user_id = user.id
    owned_cat_id = owned_cat.id
    unowned_cat_id = unowned_cat.id
    cat_asset_id = cat_asset.id
    user_public_id = user.public_id
    owned_cat_public_id = owned_cat.public_id
    unowned_cat_public_id = unowned_cat.public_id
    cat_asset_public_id = cat_asset.public_id
    headers = {
        "X-User-Public-ID": str(user_public_id),
    }

    try:
        with TestClient(app) as client:
            collection_response = client.get(
                "/api/v1/cats/collection",
                headers=headers,
            )

            assert collection_response.status_code == 200
            collection_payload = collection_response.json()
            collection_by_id = {cat["cat_public_id"]: cat for cat in collection_payload["cats"]}

            owned_entry = collection_by_id[str(owned_cat_public_id)]
            unowned_entry = collection_by_id[str(unowned_cat_public_id)]

            assert collection_payload["owned_count"] == 1
            assert collection_payload["total_count"] >= 2
            assert owned_entry == {
                "cat_public_id": str(owned_cat_public_id),
                "cat_asset_public_id": str(cat_asset_public_id),
                "name": owned_cat.name,
                "persona": owned_cat.persona,
                "rarity": "COMMON",
                "is_owned": True,
            }
            assert unowned_entry == {
                "cat_public_id": str(unowned_cat_public_id),
                "cat_asset_public_id": None,
                "name": unowned_cat.name,
                "persona": unowned_cat.persona,
                "rarity": "RARE",
                "is_owned": False,
            }

            context_response = client.get(
                (f"/api/v1/cats/{cat_asset_public_id}/conversation-context"),
                headers=headers,
            )

            assert context_response.status_code == 200
            assert context_response.json() == {
                "cat_asset_public_id": str(cat_asset_public_id),
                "cat_public_id": str(owned_cat_public_id),
                "name": owned_cat.name,
                "persona": owned_cat.persona,
                "memories": [],
            }

            first_memory_response = client.post(
                f"/api/v1/cats/{cat_asset_public_id}/memories",
                json={"context_summary": "The user studied Python loops."},
                headers=headers,
            )
            second_memory_response = client.post(
                f"/api/v1/cats/{cat_asset_public_id}/memories",
                json={"context_summary": "The user understood functions."},
                headers=headers,
            )

            assert first_memory_response.status_code == 201
            assert second_memory_response.status_code == 201

            first_memory = first_memory_response.json()
            second_memory = second_memory_response.json()

            assert set(first_memory) == {
                "public_id",
                "cat_asset_public_id",
                "context_summary",
                "created_at",
            }
            assert first_memory["cat_asset_public_id"] == str(cat_asset_public_id)
            assert second_memory["cat_asset_public_id"] == str(cat_asset_public_id)

            populated_context_response = client.get(
                (f"/api/v1/cats/{cat_asset_public_id}/conversation-context"),
                headers=headers,
            )

            assert populated_context_response.status_code == 200
            assert {
                memory["context_summary"]
                for memory in populated_context_response.json()["memories"]
            } == {
                "The user studied Python loops.",
                "The user understood functions.",
            }

            selected_delete_response = client.delete(
                (f"/api/v1/cats/{cat_asset_public_id}/memories/{first_memory['public_id']}"),
                headers=headers,
            )

            assert selected_delete_response.status_code == 204
            assert selected_delete_response.content == b""

            remaining_context_response = client.get(
                (f"/api/v1/cats/{cat_asset_public_id}/conversation-context"),
                headers=headers,
            )

            remaining_memories = remaining_context_response.json()["memories"]
            assert len(remaining_memories) == 1
            assert remaining_memories[0]["public_id"] == second_memory["public_id"]

            all_delete_response = client.delete(
                f"/api/v1/cats/{cat_asset_public_id}/memories",
                headers=headers,
            )

            assert all_delete_response.status_code == 204
            assert all_delete_response.content == b""

            final_context_response = client.get(
                (f"/api/v1/cats/{cat_asset_public_id}/conversation-context"),
                headers=headers,
            )

            assert final_context_response.status_code == 200
            final_context = final_context_response.json()
            assert final_context["persona"] == owned_cat.persona
            assert final_context["memories"] == []

        with session_factory() as verification_session:
            persisted_asset = verification_session.get(
                Asset,
                cat_asset_id,
            )
            persisted_memory = verification_session.scalar(
                select(CatMemory).where(CatMemory.cat_asset_id == cat_asset_id)
            )

            assert persisted_asset is not None
            assert persisted_asset.quantity == 1
            assert persisted_memory is None
    finally:
        with session_factory() as cleanup_session:
            cleanup_session.execute(delete(CatMemory).where(CatMemory.cat_asset_id == cat_asset_id))
            cleanup_session.execute(delete(Asset).where(Asset.id == cat_asset_id))
            cleanup_session.execute(delete(User).where(User.id == user_id))
            cleanup_session.execute(delete(Cat).where(Cat.id.in_([owned_cat_id, unowned_cat_id])))
            cleanup_session.commit()


def test_cat_chat_http_uses_database_persona_and_persists_memory(
    engine,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "test")
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    user = User(
        email=f"http-cat-chat-{uuid.uuid4()}@example.com",
        username=f"http-cat-chat-user-{uuid.uuid4()}",
        balance=0,
    )
    cat = Cat(
        name=f"chat-cat-{uuid.uuid4()}",
        persona="Playful and explain coding step by step.",
        rarity="COMMON",
    )

    with session_factory() as seed_session:
        seed_session.add_all([user, cat])
        seed_session.flush()
        cat_asset = Asset(
            user_id=user.id,
            cat_id=cat.id,
            quantity=1,
        )
        seed_session.add(cat_asset)
        seed_session.flush()
        existing_memory = CatMemory(
            cat_asset_id=cat_asset.id,
            context_summary="The user is learning Python loops.",
        )
        seed_session.add(existing_memory)
        seed_session.commit()

    user_id = user.id
    cat_id = cat.id
    cat_asset_id = cat_asset.id
    user_public_id = user.public_id
    cat_asset_public_id = cat_asset.public_id
    ai_client = MagicMock()
    ai_client.generate_structured.return_value = AIStructuredResult(
        data=CatChatGeneration(
            reply="Let's practice a for loop, meow!",
            memory_summary="The user prefers examples.",
        ),
        input_tokens=42,
        output_tokens=12,
    )
    app.dependency_overrides[get_cat_ai_client] = lambda: ai_client

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/cats/{cat_asset_public_id}/chat",
                headers={"X-User-Public-ID": str(user_public_id)},
                json={
                    "message": "Show me a loop example.",
                    "recent_messages": [{"role": "assistant", "text": "What shall we study?"}],
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["cat_asset_public_id"] == str(cat_asset_public_id)
        assert payload["reply"] == "Let's practice a for loop, meow!"
        assert payload["memory"]["context_summary"] == "The user prefers examples."
        assert payload["input_tokens"] == 42
        assert payload["output_tokens"] == 12
        assert "id" not in payload
        assert "cat_asset_id" not in payload["memory"]

        call = ai_client.generate_structured.call_args.kwargs
        assert cat.persona in call["system_instruction"]
        assert existing_memory.context_summary in call["system_instruction"]

        with session_factory() as verification_session:
            summaries = verification_session.scalars(
                select(CatMemory.context_summary).where(CatMemory.cat_asset_id == cat_asset_id)
            ).all()
            assert summaries == [
                "The user is learning Python loops.",
                "The user prefers examples.",
            ]
    finally:
        app.dependency_overrides.pop(get_cat_ai_client, None)
        with session_factory() as cleanup_session:
            cleanup_session.execute(delete(CatMemory).where(CatMemory.cat_asset_id == cat_asset_id))
            cleanup_session.execute(delete(Asset).where(Asset.id == cat_asset_id))
            cleanup_session.execute(delete(User).where(User.id == user_id))
            cleanup_session.execute(delete(Cat).where(Cat.id == cat_id))
            cleanup_session.commit()
