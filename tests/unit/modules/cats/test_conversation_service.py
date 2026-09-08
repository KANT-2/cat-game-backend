import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import (
    InvalidMemorySummaryError,
    ResourceNotFoundError,
)
from app.models.asset import Asset
from app.models.cat import Cat
from app.models.cat_memory import CatMemory
from app.models.user import User
from app.modules.cats.service import (
    add_cat_memory,
    delete_all_cat_memories,
    delete_cat_memory,
    get_cat_conversation_context,
)
from tests.fakes.repositories import (
    FakeAssetRepository,
    FakeCatMemoryRepository,
    FakeCatRepository,
    FakeUserRepository,
)


def test_get_cat_conversation_context_returns_persona_and_memories() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="cat-owner@example.com",
        username="cat-owner",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="나비",
        persona="친절하고 차분하게 코딩을 설명하는 고양이",
        rarity="COMMON",
    )
    cat_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=cat.id,
        item_id=None,
        quantity=1,
    )
    memory = CatMemory(
        id=40,
        public_id=uuid.uuid4(),
        cat_asset_id=cat_asset.id,
        context_summary="사용자는 파이썬 반복문을 공부했다.",
        created_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository([cat_asset])
    unit_of_work.cat_memories = FakeCatMemoryRepository([memory])

    result = get_cat_conversation_context(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset.public_id,
    )

    assert result.cat_asset_public_id == cat_asset.public_id
    assert result.cat_public_id == cat.public_id
    assert result.name == cat.name
    assert result.persona == cat.persona
    assert len(result.memories) == 1
    assert result.memories[0].public_id == memory.public_id
    assert result.memories[0].context_summary == memory.context_summary

    dumped = result.model_dump()
    assert "id" not in dumped
    assert "cat_id" not in dumped
    assert "cat_asset_id" not in dumped


def test_get_cat_conversation_context_hides_another_users_asset() -> None:
    requester = User(
        id=1,
        public_id=uuid.uuid4(),
        email="requester@example.com",
        username="requester",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    owner = User(
        id=2,
        public_id=uuid.uuid4(),
        email="owner@example.com",
        username="owner",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    cat_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=owner.id,
        cat_id=20,
        item_id=None,
        quantity=1,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([requester, owner])
    unit_of_work.cats = FakeCatRepository()
    unit_of_work.assets = FakeAssetRepository([cat_asset])
    unit_of_work.cat_memories = FakeCatMemoryRepository()

    with pytest.raises(
        ResourceNotFoundError,
        match="cat asset not found",
    ):
        get_cat_conversation_context(
            unit_of_work=unit_of_work,
            user_public_id=requester.public_id,
            cat_asset_public_id=cat_asset.public_id,
        )


def test_get_cat_conversation_context_rejects_item_asset() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="item-owner@example.com",
        username="item-owner",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    item_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=None,
        item_id=50,
        quantity=1,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository()
    unit_of_work.assets = FakeAssetRepository([item_asset])
    unit_of_work.cat_memories = FakeCatMemoryRepository()

    with pytest.raises(
        ResourceNotFoundError,
        match="cat asset not found",
    ):
        get_cat_conversation_context(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            cat_asset_public_id=item_asset.public_id,
        )


def test_add_cat_memory_appends_without_overwriting_existing_memory() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="memory-owner@example.com",
        username="memory-owner",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    cat_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=20,
        item_id=None,
        quantity=1,
    )
    existing_memory = CatMemory(
        id=40,
        public_id=uuid.uuid4(),
        cat_asset_id=cat_asset.id,
        context_summary="사용자는 변수에 관해 질문했다.",
        created_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.assets = FakeAssetRepository([cat_asset])
    unit_of_work.cat_memories = FakeCatMemoryRepository([existing_memory])

    result = add_cat_memory(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset.public_id,
        context_summary="사용자는 반복문 예제를 이해했다.",
    )

    memories = unit_of_work.cat_memories.memories

    assert len(memories) == 2
    assert memories[0] is existing_memory
    assert memories[0].context_summary == ("사용자는 변수에 관해 질문했다.")
    assert memories[1].context_summary == ("사용자는 반복문 예제를 이해했다.")

    assert result.public_id == memories[1].public_id
    assert result.cat_asset_public_id == cat_asset.public_id
    assert result.context_summary == memories[1].context_summary
    assert "cat_asset_id" not in result.model_dump()

    unit_of_work.commit.assert_called_once_with()


def test_delete_cat_memory_removes_only_selected_memory() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="delete-memory@example.com",
        username="delete-memory",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    cat_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=20,
        item_id=None,
        quantity=1,
    )
    first_memory = CatMemory(
        id=40,
        public_id=uuid.uuid4(),
        cat_asset_id=cat_asset.id,
        context_summary="첫 번째 기억",
        created_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
    )
    second_memory = CatMemory(
        id=41,
        public_id=uuid.uuid4(),
        cat_asset_id=cat_asset.id,
        context_summary="두 번째 기억",
        created_at=datetime(2026, 9, 4, 13, 0, tzinfo=UTC),
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.assets = FakeAssetRepository([cat_asset])
    unit_of_work.cat_memories = FakeCatMemoryRepository([first_memory, second_memory])

    delete_cat_memory(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset.public_id,
        memory_public_id=first_memory.public_id,
    )

    assert unit_of_work.cat_memories.memories == [second_memory]
    assert unit_of_work.assets.assets == [cat_asset]
    unit_of_work.commit.assert_called_once_with()


def test_delete_all_cat_memories_removes_only_target_cats_memories() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="delete-all@example.com",
        username="delete-all",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    target_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=20,
        item_id=None,
        quantity=1,
    )
    other_asset = Asset(
        id=31,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=21,
        item_id=None,
        quantity=1,
    )
    target_memories = [
        CatMemory(
            id=40,
            public_id=uuid.uuid4(),
            cat_asset_id=target_asset.id,
            context_summary="첫 번째 기억",
            created_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
        ),
        CatMemory(
            id=41,
            public_id=uuid.uuid4(),
            cat_asset_id=target_asset.id,
            context_summary="두 번째 기억",
            created_at=datetime(2026, 9, 4, 13, 0, tzinfo=UTC),
        ),
    ]
    other_memory = CatMemory(
        id=42,
        public_id=uuid.uuid4(),
        cat_asset_id=other_asset.id,
        context_summary="다른 고양이의 기억",
        created_at=datetime(2026, 9, 4, 14, 0, tzinfo=UTC),
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.assets = FakeAssetRepository([target_asset, other_asset])
    unit_of_work.cat_memories = FakeCatMemoryRepository([*target_memories, other_memory])

    delete_all_cat_memories(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        cat_asset_public_id=target_asset.public_id,
    )

    assert unit_of_work.cat_memories.memories == [other_memory]
    assert unit_of_work.assets.assets == [
        target_asset,
        other_asset,
    ]
    unit_of_work.commit.assert_called_once_with()


def test_delete_cat_memory_rejects_memory_from_another_cat() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="memory-scope@example.com",
        username="memory-scope",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    requested_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=20,
        item_id=None,
        quantity=1,
    )
    other_asset = Asset(
        id=31,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=21,
        item_id=None,
        quantity=1,
    )
    other_memory = CatMemory(
        id=40,
        public_id=uuid.uuid4(),
        cat_asset_id=other_asset.id,
        context_summary="다른 고양이의 기억",
        created_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.assets = FakeAssetRepository([requested_asset, other_asset])
    unit_of_work.cat_memories = FakeCatMemoryRepository([other_memory])

    with pytest.raises(
        ResourceNotFoundError,
        match="cat memory not found",
    ):
        delete_cat_memory(
            unit_of_work=unit_of_work,
            user_public_id=user.public_id,
            cat_asset_public_id=requested_asset.public_id,
            memory_public_id=other_memory.public_id,
        )

    assert unit_of_work.cat_memories.memories == [other_memory]
    unit_of_work.commit.assert_not_called()


def test_delete_all_cat_memories_hides_another_users_asset() -> None:
    requester = User(
        id=1,
        public_id=uuid.uuid4(),
        email="requester-delete@example.com",
        username="requester-delete",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    owner = User(
        id=2,
        public_id=uuid.uuid4(),
        email="owner-delete@example.com",
        username="owner-delete",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    cat_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=owner.id,
        cat_id=20,
        item_id=None,
        quantity=1,
    )
    memory = CatMemory(
        id=40,
        public_id=uuid.uuid4(),
        cat_asset_id=cat_asset.id,
        context_summary="소유자만 삭제할 수 있는 기억",
        created_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([requester, owner])
    unit_of_work.assets = FakeAssetRepository([cat_asset])
    unit_of_work.cat_memories = FakeCatMemoryRepository([memory])

    with pytest.raises(
        ResourceNotFoundError,
        match="cat asset not found",
    ):
        delete_all_cat_memories(
            unit_of_work=unit_of_work,
            user_public_id=requester.public_id,
            cat_asset_public_id=cat_asset.public_id,
        )

    assert unit_of_work.cat_memories.memories == [memory]
    assert unit_of_work.assets.assets == [cat_asset]
    unit_of_work.commit.assert_not_called()


def test_get_cat_conversation_context_orders_memories_oldest_first() -> None:
    user = User(
        id=1,
        public_id=uuid.uuid4(),
        email="ordered-memory@example.com",
        username="ordered-memory",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    cat = Cat(
        id=20,
        public_id=uuid.uuid4(),
        name="나비",
        persona="차분한 코딩 선생님",
        rarity="COMMON",
    )
    cat_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=user.id,
        cat_id=cat.id,
        item_id=None,
        quantity=1,
    )
    older_memory = CatMemory(
        id=40,
        public_id=uuid.uuid4(),
        cat_asset_id=cat_asset.id,
        context_summary="먼저 생성된 기억",
        created_at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
    )
    newer_memory = CatMemory(
        id=41,
        public_id=uuid.uuid4(),
        cat_asset_id=cat_asset.id,
        context_summary="나중에 생성된 기억",
        created_at=datetime(2026, 9, 4, 13, 0, tzinfo=UTC),
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([user])
    unit_of_work.cats = FakeCatRepository([cat])
    unit_of_work.assets = FakeAssetRepository([cat_asset])
    unit_of_work.cat_memories = FakeCatMemoryRepository([newer_memory, older_memory])

    result = get_cat_conversation_context(
        unit_of_work=unit_of_work,
        user_public_id=user.public_id,
        cat_asset_public_id=cat_asset.public_id,
    )

    assert [memory.context_summary for memory in result.memories] == [
        "먼저 생성된 기억",
        "나중에 생성된 기억",
    ]


def test_add_cat_memory_rejects_blank_context_summary() -> None:
    unit_of_work = MagicMock()

    with pytest.raises(
        InvalidMemorySummaryError,
        match="context summary must not be blank",
    ):
        add_cat_memory(
            unit_of_work=unit_of_work,
            user_public_id=uuid.uuid4(),
            cat_asset_public_id=uuid.uuid4(),
            context_summary="   ",
        )

    unit_of_work.__enter__.assert_not_called()


def test_add_cat_memory_hides_another_users_asset() -> None:
    requester = User(
        id=1,
        public_id=uuid.uuid4(),
        email="memory-requester@example.com",
        username="memory-requester",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    owner = User(
        id=2,
        public_id=uuid.uuid4(),
        email="memory-owner-2@example.com",
        username="memory-owner-2",
        role="STUDENT",
        balance=1000,
        mileage=0,
        house_level=1,
    )
    cat_asset = Asset(
        id=30,
        public_id=uuid.uuid4(),
        user_id=owner.id,
        cat_id=20,
        item_id=None,
        quantity=1,
    )

    unit_of_work = MagicMock()
    unit_of_work.__enter__.return_value = unit_of_work
    unit_of_work.users = FakeUserRepository([requester, owner])
    unit_of_work.assets = FakeAssetRepository([cat_asset])
    unit_of_work.cat_memories = FakeCatMemoryRepository()

    with pytest.raises(
        ResourceNotFoundError,
        match="cat asset not found",
    ):
        add_cat_memory(
            unit_of_work=unit_of_work,
            user_public_id=requester.public_id,
            cat_asset_public_id=cat_asset.public_id,
            context_summary="추가되면 안 되는 기억",
        )

    assert unit_of_work.cat_memories.memories == []
    unit_of_work.commit.assert_not_called()
