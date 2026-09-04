import uuid
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.core.repository_contracts import ClaimStatus
from app.db.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyCatMemoryRepository,
    SqlAlchemyCatRepository,
    SqlAlchemyExecutionRepository,
    SqlAlchemyItemRepository,
    SqlAlchemyPlacedObjectRepository,
    SqlAlchemyUserRepository,
)
from app.models.asset import Asset
from app.models.cat_memory import CatMemory
from app.models.gacha_execution import GachaExecution
from app.models.placed_object import PlacedObject


def _compile_sql(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_user_repository_gets_by_public_id_without_lock() -> None:
    session = Mock(spec=Session)
    expected_user = object()
    session.execute.return_value.scalar_one_or_none.return_value = expected_user
    repository = SqlAlchemyUserRepository(session)
    public_id = uuid.uuid4()

    result = repository.get_by_public_id(public_id)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result is expected_user
    assert "WHERE users.public_id =" in sql
    assert "FOR UPDATE" not in sql
    session.commit.assert_not_called()


def test_user_repository_gets_for_update_with_row_lock() -> None:
    session = Mock(spec=Session)
    expected_user = object()
    session.execute.return_value.scalar_one_or_none.return_value = expected_user
    repository = SqlAlchemyUserRepository(session)

    result = repository.get_for_update(1)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result is expected_user
    assert "WHERE users.id = 1" in sql
    assert "FOR UPDATE" in sql
    session.commit.assert_not_called()

def test_item_repository_gets_by_public_id() -> None:
    session = Mock(spec=Session)
    expected_item = object()
    session.execute.return_value.scalar_one_or_none.return_value = expected_item
    repository = SqlAlchemyItemRepository(session)
    public_id = uuid.uuid4()

    result = repository.get_by_public_id(public_id)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result is expected_item
    assert "WHERE items.public_id =" in sql
    assert "FOR UPDATE" not in sql
    session.commit.assert_not_called()


def test_cat_repository_gets_by_public_id() -> None:
    session = Mock(spec=Session)
    expected_cat = object()
    session.execute.return_value.scalar_one_or_none.return_value = expected_cat
    repository = SqlAlchemyCatRepository(session)
    public_id = uuid.uuid4()

    result = repository.get_by_public_id(public_id)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result is expected_cat
    assert "WHERE cats.public_id =" in sql
    assert "FOR UPDATE" not in sql
    session.commit.assert_not_called()

def test_cat_repository_gets_by_internal_id() -> None:
    session = Mock(spec=Session)
    expected_cat = object()
    session.execute.return_value.scalar_one_or_none.return_value = (
        expected_cat
    )
    repository = SqlAlchemyCatRepository(session)

    result = repository.get_by_id(20)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result is expected_cat
    assert "WHERE cats.id = 20" in sql
    assert "FOR UPDATE" not in sql
    session.commit.assert_not_called()

def test_asset_repository_gets_by_public_id() -> None:
    session = Mock(spec=Session)
    expected_asset = object()
    session.execute.return_value.scalar_one_or_none.return_value = (
        expected_asset
    )
    repository = SqlAlchemyAssetRepository(session)
    public_id = uuid.uuid4()

    result = repository.get_by_public_id(public_id)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result is expected_asset
    assert "WHERE assets.public_id =" in sql
    assert "FOR UPDATE" not in sql
    session.commit.assert_not_called()

def test_asset_repository_gets_cat_asset_without_lock() -> None:
    session = Mock(spec=Session)
    expected_asset = object()
    session.execute.return_value.scalar_one_or_none.return_value = expected_asset
    repository = SqlAlchemyAssetRepository(session)

    result = repository.get_cat_asset(user_id=1, cat_id=10)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result is expected_asset
    assert "assets.user_id = 1" in sql
    assert "assets.cat_id = 10" in sql
    assert "FOR UPDATE" not in sql
    session.commit.assert_not_called()


def test_asset_repository_locks_item_asset() -> None:
    session = Mock(spec=Session)
    expected_asset = object()
    session.execute.return_value.scalar_one_or_none.return_value = expected_asset
    repository = SqlAlchemyAssetRepository(session)

    result = repository.get_item_asset_for_update(
        user_id=1,
        item_id=20,
    )

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result is expected_asset
    assert "assets.user_id = 1" in sql
    assert "assets.item_id = 20" in sql
    assert "FOR UPDATE" in sql
    session.commit.assert_not_called()

def test_asset_repository_adds_to_existing_item_quantity() -> None:
    session = Mock(spec=Session)
    existing = Asset(
        id=1,
        public_id=uuid.uuid4(),
        user_id=1,
        cat_id=None,
        item_id=20,
        quantity=2,
    )
    repository = SqlAlchemyAssetRepository(session)
    repository.get_item_asset_for_update = Mock(return_value=existing)

    result = repository.add_item_quantity(
        user_id=1,
        item_id=20,
        quantity=3,
    )

    assert result is existing
    assert existing.quantity == 5
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_asset_repository_adds_new_item_asset() -> None:
    session = Mock(spec=Session)
    repository = SqlAlchemyAssetRepository(session)
    repository.get_item_asset_for_update = Mock(return_value=None)

    result = repository.add_item_quantity(
        user_id=1,
        item_id=20,
        quantity=2,
    )

    assert result.user_id == 1
    assert result.cat_id is None
    assert result.item_id == 20
    assert result.quantity == 2
    session.add.assert_called_once_with(result)
    session.commit.assert_not_called()


def test_asset_repository_grants_new_cat() -> None:
    session = Mock(spec=Session)
    repository = SqlAlchemyAssetRepository(session)
    repository.get_cat_asset = Mock(return_value=None)

    result = repository.grant_cat(user_id=1, cat_id=10)

    assert result.user_id == 1
    assert result.cat_id == 10
    assert result.item_id is None
    assert result.quantity == 1
    session.add.assert_called_once_with(result)
    session.commit.assert_not_called()

def test_placed_object_repository_counts_locked_rows() -> None:
    session = Mock(spec=Session)
    session.execute.return_value.scalars.return_value.all.return_value = [
        object(),
        object(),
    ]
    repository = SqlAlchemyPlacedObjectRepository(session)

    result = repository.count_for_update(user_id=1, item_id=20)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result == 2
    assert "placed_objects.user_id = 1" in sql
    assert "placed_objects.item_id = 20" in sql
    assert "FOR UPDATE" in sql
    session.commit.assert_not_called()


def test_placed_object_repository_adds_object() -> None:
    session = Mock(spec=Session)
    repository = SqlAlchemyPlacedObjectRepository(session)
    position_data = {"x": 120, "y": 80, "z": 0}

    result = repository.add(
        user_id=1,
        item_id=20,
        position_data=position_data,
    )

    assert result.user_id == 1
    assert result.item_id == 20
    assert result.position_data == position_data
    session.add.assert_called_once_with(result)
    session.commit.assert_not_called()

def test_cat_memory_repository_locks_by_public_id() -> None:
    session = Mock(spec=Session)
    expected_memory = object()
    session.execute.return_value.scalar_one_or_none.return_value = (
        expected_memory
    )
    repository = SqlAlchemyCatMemoryRepository(session)
    public_id = uuid.uuid4()

    result = repository.get_by_public_id_for_update(public_id)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result is expected_memory
    assert "WHERE cat_memories.public_id =" in sql
    assert "FOR UPDATE" in sql
    session.commit.assert_not_called()

def test_cat_memory_repository_removes_memory() -> None:
    session = Mock(spec=Session)
    repository = SqlAlchemyCatMemoryRepository(session)
    memory = Mock(spec=CatMemory)

    repository.remove(memory)

    session.delete.assert_called_once_with(memory)
    session.commit.assert_not_called()

def test_cat_memory_repository_removes_all_for_cat_asset() -> None:
    session = Mock(spec=Session)
    repository = SqlAlchemyCatMemoryRepository(session)

    repository.remove_all_by_cat_asset_id(cat_asset_id=30)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert "DELETE FROM cat_memories" in sql
    assert "cat_memories.cat_asset_id = 30" in sql
    session.commit.assert_not_called()

def test_cat_memory_repository_lists_memories_in_order() -> None:
    session = Mock(spec=Session)
    expected_memories = [object(), object()]
    session.execute.return_value.scalars.return_value.all.return_value = (
        expected_memories
    )
    repository = SqlAlchemyCatMemoryRepository(session)

    result = repository.list_by_cat_asset_id(cat_asset_id=30)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result == expected_memories
    assert "cat_memories.cat_asset_id = 30" in sql
    assert "ORDER BY cat_memories.created_at, cat_memories.id" in sql
    assert "FOR UPDATE" not in sql
    session.commit.assert_not_called()


def test_cat_memory_repository_adds_new_memory() -> None:
    session = Mock(spec=Session)
    repository = SqlAlchemyCatMemoryRepository(session)

    result = repository.add(
        cat_asset_id=30,
        context_summary="The user learned about loops.",
    )

    assert result.cat_asset_id == 30
    assert result.context_summary == "The user learned about loops."
    session.add.assert_called_once_with(result)
    session.commit.assert_not_called()

def test_execution_repository_completes_execution() -> None:
    session = Mock(spec=Session)
    repository = SqlAlchemyExecutionRepository(session)
    execution = GachaExecution(
        id=1,
        public_id=uuid.uuid4(),
        user_id=1,
        request_id=uuid.uuid4(),
        request_payload={"draw_count": 1},
        request_hash="a" * 64,
        operation_type="GACHA",
        status=ClaimStatus.ACQUIRED,
        draw_count=1,
        balance_cost=0,
        result_data=None,
        created_at=datetime.now(UTC),
        completed_at=None,
    )
    result_data = {"cat_public_id": str(uuid.uuid4())}
    started_at = datetime.now(UTC)

    repository.complete(
        execution,
        balance_cost=100,
        result_data=result_data,
    )

    assert execution.balance_cost == 100
    assert execution.result_data == result_data
    assert execution.status == ClaimStatus.COMPLETED
    assert execution.completed_at is not None
    assert execution.completed_at >= started_at
    session.commit.assert_not_called()


def test_execution_repository_rejects_negative_cost() -> None:
    session = Mock(spec=Session)
    repository = SqlAlchemyExecutionRepository(session)
    execution = GachaExecution()

    with pytest.raises(ValueError, match="nonnegative"):
        repository.complete(
            execution,
            balance_cost=-1,
            result_data={},
        )

    session.commit.assert_not_called()

def test_execution_repository_claims_new_request_atomically() -> None:
    session = Mock(spec=Session)
    inserted_execution = GachaExecution()
    session.execute.return_value.scalar_one_or_none.return_value = (
        inserted_execution
    )
    repository = SqlAlchemyExecutionRepository(session)
    request_id = uuid.uuid4()
    request_payload = {"draw_count": 1}

    result = repository.claim(
        user_id=1,
        request_id=request_id,
        request_hash="a" * 64,
        request_payload=request_payload,
        operation_type="GACHA",
    )

    statement = session.execute.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    params = compiled.params

    assert "INSERT INTO gacha_executions" in sql
    assert "ON CONFLICT (request_id) DO NOTHING" in sql
    assert "RETURNING" in sql
    assert params["user_id"] == 1
    assert params["request_id"] == request_id
    assert params["request_hash"] == "a" * 64
    assert params["request_payload"] == request_payload
    assert params["operation_type"] == "GACHA"
    assert params["status"] == ClaimStatus.ACQUIRED
    assert params["balance_cost"] == 0
    assert result.status == ClaimStatus.ACQUIRED
    assert result.execution is inserted_execution
    session.commit.assert_not_called()

def _repository_with_existing_execution(
    existing: GachaExecution,
) -> tuple[Mock, SqlAlchemyExecutionRepository]:
    session = Mock(spec=Session)

    insert_result = Mock()
    insert_result.scalar_one_or_none.return_value = None

    select_result = Mock()
    select_result.scalar_one.return_value = existing

    session.execute.side_effect = [insert_result, select_result]
    return session, SqlAlchemyExecutionRepository(session)


def test_execution_repository_returns_completed_execution() -> None:
    existing = GachaExecution(
        user_id=1,
        request_hash="a" * 64,
        status=ClaimStatus.COMPLETED,
        result_data={"reward": "cat"},
    )
    session, repository = _repository_with_existing_execution(existing)
    request_id = uuid.uuid4()

    result = repository.claim(
        user_id=1,
        request_id=request_id,
        request_hash="a" * 64,
        request_payload={"draw_count": 1},
        operation_type="GACHA",
    )

    select_statement = session.execute.call_args_list[1].args[0]
    sql = _compile_sql(select_statement)

    assert "gacha_executions.request_id =" in sql
    assert "FOR UPDATE" in sql
    assert result.status == ClaimStatus.COMPLETED
    assert result.execution is existing
    session.commit.assert_not_called()


def test_execution_repository_returns_acquired_execution() -> None:
    existing = GachaExecution(
        user_id=1,
        request_hash="a" * 64,
        status=ClaimStatus.ACQUIRED,
    )
    session, repository = _repository_with_existing_execution(existing)

    result = repository.claim(
        user_id=1,
        request_id=uuid.uuid4(),
        request_hash="a" * 64,
        request_payload={"draw_count": 1},
        operation_type="GACHA",
    )

    assert result.status == ClaimStatus.ACQUIRED
    assert result.execution is existing
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    ("existing_user_id", "existing_request_hash"),
    [
        (2, "a" * 64),
        (1, "b" * 64),
    ],
)
def test_execution_repository_detects_claim_conflict(
    existing_user_id: int,
    existing_request_hash: str,
) -> None:
    existing = GachaExecution(
        user_id=existing_user_id,
        request_hash=existing_request_hash,
        status=ClaimStatus.COMPLETED,
    )
    session, repository = _repository_with_existing_execution(existing)

    result = repository.claim(
        user_id=1,
        request_id=uuid.uuid4(),
        request_hash="a" * 64,
        request_payload={"draw_count": 1},
        operation_type="GACHA",
    )

    assert result.status == ClaimStatus.HASH_CONFLICT
    assert result.execution is existing
    session.commit.assert_not_called()

def test_item_repository_gets_by_internal_id() -> None:
    session = Mock(spec=Session)
    expected_item = object()
    session.execute.return_value.scalar_one_or_none.return_value = (
        expected_item
    )
    repository = SqlAlchemyItemRepository(session)

    result = repository.get_by_id(20)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result is expected_item
    assert "WHERE items.id = 20" in sql
    assert "FOR UPDATE" not in sql
    session.commit.assert_not_called()


def test_placed_object_repository_locks_by_public_id() -> None:
    session = Mock(spec=Session)
    expected_placement = object()
    session.execute.return_value.scalar_one_or_none.return_value = (
        expected_placement
    )
    repository = SqlAlchemyPlacedObjectRepository(session)
    public_id = uuid.uuid4()

    result = repository.get_by_public_id_for_update(public_id)

    statement = session.execute.call_args.args[0]
    sql = _compile_sql(statement)

    assert result is expected_placement
    assert "WHERE placed_objects.public_id =" in sql
    assert "FOR UPDATE" in sql
    session.commit.assert_not_called()


def test_placed_object_repository_removes_object() -> None:
    session = Mock(spec=Session)
    repository = SqlAlchemyPlacedObjectRepository(session)
    placed_object = PlacedObject()

    repository.remove(placed_object)

    session.delete.assert_called_once_with(placed_object)
    session.commit.assert_not_called()
