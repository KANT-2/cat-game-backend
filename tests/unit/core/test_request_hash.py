import uuid

from app.core.request_hash import build_request_hash


def test_key_order_does_not_change_hash() -> None:
    item_public_id = uuid.uuid4()

    first = {
        "item_public_id": item_public_id,
        "quantity": 2,
    }
    second = {
        "quantity": 2,
        "item_public_id": item_public_id,
    }

    assert build_request_hash(
        operation_type="ITEM_PURCHASE",
        payload=first,
    ) == build_request_hash(
        operation_type="ITEM_PURCHASE",
        payload=second,
    )


def test_request_id_is_excluded_from_hash() -> None:
    first = {"request_id": uuid.uuid4(), "quantity": 2}
    second = {"request_id": uuid.uuid4(), "quantity": 2}

    assert build_request_hash(
        operation_type="ITEM_PURCHASE",
        payload=first,
    ) == build_request_hash(
        operation_type="ITEM_PURCHASE",
        payload=second,
    )


def test_server_decided_values_are_excluded() -> None:
    first = {"quantity": 2, "price": 100, "balance": 900, "mileage": 0}
    second = {"quantity": 2, "price": 999, "balance": 1, "mileage": 50}

    assert build_request_hash(
        operation_type="ITEM_PURCHASE",
        payload=first,
    ) == build_request_hash(
        operation_type="ITEM_PURCHASE",
        payload=second,
    )


def test_operation_type_changes_hash() -> None:
    payload = {"quantity": 1}

    assert build_request_hash(
        operation_type="ITEM_PURCHASE",
        payload=payload,
    ) != build_request_hash(
        operation_type="CAT_GACHA",
        payload=payload,
    )


def test_request_content_changes_hash() -> None:
    assert build_request_hash(
        operation_type="ITEM_PURCHASE",
        payload={"quantity": 1},
    ) != build_request_hash(
        operation_type="ITEM_PURCHASE",
        payload={"quantity": 2},
    )
