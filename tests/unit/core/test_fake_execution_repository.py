import uuid

from app.core.repository_contracts import ClaimStatus
from tests.fakes.repositories import FakeExecutionRepository


def test_fake_execution_repository_claim_and_complete() -> None:
    repository = FakeExecutionRepository()
    request_id = uuid.uuid4()

    acquired = repository.claim(
        user_id=1,
        request_id=request_id,
        request_hash="same-hash",
        request_payload={"quantity": 1},
        operation_type="CAT_GACHA",
    )

    assert acquired.status is ClaimStatus.ACQUIRED
    assert acquired.execution.balance_cost == 0
    assert acquired.execution.status == "ACQUIRED"

    repository.complete(
        acquired.execution,
        balance_cost=100,
        result_data={"cat_public_id": str(uuid.uuid4())},
    )

    replayed = repository.claim(
        user_id=1,
        request_id=request_id,
        request_hash="same-hash",
        request_payload={"quantity": 1},
        operation_type="CAT_GACHA",
    )

    assert replayed.status is ClaimStatus.COMPLETED
    assert replayed.execution is acquired.execution
    assert replayed.execution.balance_cost == 100
    assert replayed.execution.status == "COMPLETED"


def test_fake_execution_repository_detects_conflicts() -> None:
    repository = FakeExecutionRepository()
    request_id = uuid.uuid4()

    repository.claim(
        user_id=1,
        request_id=request_id,
        request_hash="original-hash",
        request_payload={"quantity": 1},
        operation_type="ITEM_PURCHASE",
    )

    hash_conflict = repository.claim(
        user_id=1,
        request_id=request_id,
        request_hash="different-hash",
        request_payload={"quantity": 2},
        operation_type="ITEM_PURCHASE",
    )
    user_conflict = repository.claim(
        user_id=2,
        request_id=request_id,
        request_hash="original-hash",
        request_payload={"quantity": 1},
        operation_type="ITEM_PURCHASE",
    )

    assert hash_conflict.status is ClaimStatus.HASH_CONFLICT
    assert user_conflict.status is ClaimStatus.HASH_CONFLICT
