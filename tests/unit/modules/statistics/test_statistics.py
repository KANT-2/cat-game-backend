import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.time import game_today
from app.main import app
from app.models.game_activity_event import GameActivityEvent
from app.models.user import User
from app.modules.statistics.router import _resolve_range, _validate_range
from app.modules.statistics.service import (
    GAME_ENTERED,
    record_game_entry,
    user_daily_learning_statistics_for_user,
)


class _RecordingSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1


def test_game_entry_is_append_only_and_privacy_minimal() -> None:
    db = _RecordingSession()
    user = User(id=17, email="private@example.com", username="learner", role="STUDENT")

    record_game_entry(db, user)  # type: ignore[arg-type]

    assert db.commits == 1
    assert len(db.added) == 1
    event = db.added[0]
    assert isinstance(event, GameActivityEvent)
    assert event.user_id == 17
    assert event.event_type == GAME_ENTERED
    assert not hasattr(event, "email")
    assert not hasattr(event, "submitted_code")


@pytest.mark.parametrize(
    ("date_from", "date_to", "detail"),
    [
        (date(2026, 9, 16), date(2026, 9, 15), "date-from-must-not-exceed-date-to"),
        (date(2025, 1, 1), date(2026, 1, 3), "statistics-range-too-large"),
    ],
)
def test_statistics_date_range_is_bounded(date_from: date, date_to: date, detail: str) -> None:
    with pytest.raises(HTTPException) as raised:
        _validate_range(date_from, date_to)

    assert raised.value.status_code == 422
    assert raised.value.detail == detail


def test_statistics_api_is_team_key_protected_without_member_login() -> None:
    paths = app.openapi()["paths"]

    for path in ("/api/v1/statistics/daily", "/api/v1/statistics/users/daily"):
        headers = {
            parameter["name"]
            for parameter in paths[path]["get"]["parameters"]
            if parameter["in"] == "header"
        }
        assert "X-API-Key" in headers
        assert "X-User-Public-ID" not in headers


def test_player_statistics_api_requires_login_not_team_key() -> None:
    paths = app.openapi()["paths"]

    for path in ("/api/v1/statistics/public/daily", "/api/v1/statistics/me/daily"):
        headers = {
            parameter["name"]
            for parameter in paths[path]["get"]["parameters"]
            if parameter["in"] == "header"
        }
        assert "X-API-Key" not in headers


@pytest.mark.parametrize(
    "path",
    ["/api/v1/statistics/public/daily", "/api/v1/statistics/me/daily"],
)
def test_player_statistics_api_rejects_unauthenticated_requests(path: str) -> None:
    response = TestClient(app).get(path)

    assert response.status_code == 401


def test_resolve_range_defaults_to_recent_lookback_window() -> None:
    date_from, date_to = _resolve_range(None, None)

    assert date_to == game_today()
    assert (date_to - date_from).days == 13


class _RecordingQuerySession:
    def __init__(self) -> None:
        self.executed: tuple[object, dict] | None = None

    def execute(self, statement: object, params: dict | None = None) -> list:
        self.executed = (statement, params or {})
        return []


def test_my_daily_statistics_query_is_scoped_to_one_user() -> None:
    db = _RecordingQuerySession()
    target_user = uuid.uuid4()

    rows = user_daily_learning_statistics_for_user(db, target_user, date(2026, 9, 1), date(2026, 9, 14))  # type: ignore[arg-type]

    assert rows == []
    assert db.executed is not None
    statement, params = db.executed
    assert "user_public_id = :user_public_id" in str(statement)
    assert "username" not in str(statement)
    assert params["user_public_id"] == target_user
