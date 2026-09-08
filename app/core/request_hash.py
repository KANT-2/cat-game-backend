import hashlib
import json
import uuid
from collections.abc import Mapping

_EXCLUDED_FIELDS = frozenset(
    {
        "request_id",
        "price",
        "balance",
        "mileage",
        "balance_cost",
    }
)


def _normalize_value(value: object) -> object:
    if isinstance(value, uuid.UUID):
        return str(value)

    if isinstance(value, Mapping):
        return {str(key): _normalize_value(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]

    return value


def build_request_hash(
    *,
    operation_type: str,
    payload: Mapping[str, object],
) -> str:
    canonical_payload = {
        key: _normalize_value(value)
        for key, value in payload.items()
        if key not in _EXCLUDED_FIELDS
    }
    canonical_payload["operation_type"] = operation_type

    canonical_json = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
