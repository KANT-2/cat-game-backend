"""Run against the disposable DATABASE_URL used by the rest of the integration suite."""

import psycopg
import pytest
from pydantic import SecretStr
from sqlalchemy import text

from app.core.config import Settings
from app.integrations.ax_platform import PlatformRepository, PlatformService, PlatformUnavailable


@pytest.fixture
def platform(engine):
    # CREATE (not REPLACE) refuses to overwrite any pre-existing integration view.
    with engine.begin() as connection:
        connection.execute(
            text("""
            CREATE VIEW public.ax_user_team_login_view AS
            SELECT 42::bigint AS user_id, 'ax@example.test'::text AS user_email,
                   NULL::text AS primary_email, 'Summer'::text AS first_name,
                   NULL::text AS last_name, 'Round Name'::text AS display_name_snapshot,
                   '/avatar.png'::text AS profile_image, 'Team A'::text AS team_name
        """)
        )
        connection.execute(
            text("""
            CREATE VIEW public.user_round_team_view AS
            SELECT * FROM (VALUES
                (42::bigint, 1::bigint, 'Round 1', 'CLOSED', 10::bigint, 'Summer',
                 100::bigint, 1, 'Team A'),
                (42, 2, 'Round 2', 'OPEN', 11, 'Summer', 200, 2, 'Team B'),
                (99, 2, 'Round 2', 'OPEN', 12, 'Other', 300, 3, 'Other Team')
            ) AS r(user_id, round_id, round_title, round_status, participant_id,
                   display_name_snapshot, team_id, team_number, team_name)
        """)
        )
    service = PlatformService(
        Settings(
            _env_file=None,
            ax_platform_database_url=SecretStr(engine.url.render_as_string(hide_password=False)),
            ax_platform_statement_timeout_ms=50,
        )
    )
    try:
        yield service
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP VIEW public.user_round_team_view"))
            connection.execute(text("DROP VIEW public.ax_user_team_login_view"))


def test_real_views_profile_history_filter_and_missing_user(platform):
    profile = platform.enrich(42)
    assert profile.status == "available"
    assert profile.profile.profile_image == "/avatar.png"
    assert profile.profile.team_name == "Team A"
    assert [row.team_name for row in platform.round_teams(42)] == ["Team A", "Team B"]
    assert [row.team_name for row in platform.round_teams(42, 2)] == ["Team B"]
    assert platform.round_teams(42, 99) == []
    assert platform.round_teams(12345) == []
    assert platform.enrich(12345).status == "not_found"


def test_real_connection_rejects_writes(platform, monkeypatch):
    def attempt_write(repository, user_id):
        assert repository.connection.execute("SHOW transaction_read_only").fetchone() == {
            "transaction_read_only": "on"
        }
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            repository.connection.execute("CREATE TABLE ax_forbidden_write (id int)")
        raise psycopg.OperationalError("write rejected")

    monkeypatch.setattr(PlatformRepository, "get_profile", attempt_write)
    assert platform.enrich(42).status == "unavailable"


def test_real_statement_timeout_is_sanitized(platform, monkeypatch):
    def slow_query(repository, user_id, round_id):
        repository.connection.execute("SELECT pg_sleep(1)")

    monkeypatch.setattr(PlatformRepository, "list_round_teams", slow_query)
    with pytest.raises(PlatformUnavailable, match="^ax-platform-unavailable$"):
        platform.round_teams(42)


def test_bridge_to_game_to_view_http_mapping(platform, db_session, monkeypatch):
    from unittest.mock import AsyncMock, Mock

    from fastapi.testclient import TestClient

    from app.api import dependencies
    from app.core.config import settings
    from app.integrations.ax_platform import get_platform_service
    from app.main import create_app

    response = Mock(status_code=200)
    response.json.return_value = {
        "id": 42,
        "display_name": "Bridge Name",
        "role": "student",
        "email": "bridge@example.test",
    }
    client = AsyncMock()
    client.get.return_value = response
    client.__aenter__.return_value = client
    monkeypatch.setattr(dependencies.httpx, "AsyncClient", Mock(return_value=client))
    monkeypatch.setattr(settings, "ax_auth_base_url", "http://bridge.test")
    app = create_app()
    app.dependency_overrides[dependencies.get_db] = lambda: db_session
    app.dependency_overrides[get_platform_service] = lambda: platform
    with TestClient(app) as http:
        http.cookies.set("sessionid", "test-session")
        result = http.get("/api/v1/session/me")
        assert result.status_code == 200
        body = result.json()
        assert body["username"] == "Bridge Name"
        assert body["email"] == "bridge@example.test"
        assert body["platform"]["profile"]["user_email"] == "ax@example.test"
        assert body["platform"]["profile"]["team_name"] == "Team A"
        assert "homepage_user_id" not in body
        assert "user_id" not in body["platform"]["profile"]
        assert len(http.get("/api/v1/session/me/round-teams").json()) == 2
        response.status_code = 401
        read = Mock()
        monkeypatch.setattr(platform, "_read", read)
        assert http.get("/api/v1/session/me").status_code == 401
        read.assert_not_called()
