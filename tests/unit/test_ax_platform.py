from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.requests import Request

from app.api.dependencies import HostUser, resolve_current_user
from app.core.config import Settings, settings
from app.integrations.ax_platform import (
    PlatformEnrichment,
    PlatformProfile,
    PlatformRepository,
    PlatformService,
    PlatformUnavailable,
    get_platform_service,
)
from app.main import create_app
from app.models.user import User
from app.modules.identity.router import _session_platform_enrichment, _trusted_profile_image_url


def config():
    return Settings(
        _env_file=None,
        ax_platform_database_url=SecretStr(
            "postgresql://ax_evaluation:test-secret@localhost/ax_evaluation"
        ),
    )


@pytest.mark.parametrize("round_id", [None, 12, "12 OR 1=1"])
def test_repository_binds_user_and_optional_round(round_id):
    connection = Mock()
    repository = PlatformRepository(connection)
    repository.list_round_teams(42, round_id)
    query, params = connection.execute.call_args.args
    assert params == ((42,) if round_id is None else (42, round_id))
    assert "WHERE user_id = %s" in query
    assert ("AND round_id = %s" in query) == (round_id is not None)
    assert "12 OR" not in query
    repository.get_profile(42)
    assert connection.execute.call_args.args[1] == (42,)
    connection.commit.assert_not_called()


def test_read_only_connection_closes_and_profile_excludes_privileges(monkeypatch):
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = {
        "profile_image": "/avatar.png",
        "team_name": "Team A",
        "is_superuser": True,
    }
    connect = Mock(return_value=connection)
    monkeypatch.setattr("app.integrations.ax_platform.psycopg.connect", connect)
    result = PlatformService(config()).enrich(42)
    assert result.status == "available"
    assert result.profile.team_name == "Team A"
    assert "is_superuser" not in result.profile.model_dump()
    assert connection.read_only is True
    assert "default_transaction_read_only=on" in connect.call_args.kwargs["options"]
    assert "statement_timeout=1000" in connect.call_args.kwargs["options"]
    assert connect.call_args.kwargs["connect_timeout"] == 3
    connection.close.assert_called_once()
    connection.commit.assert_not_called()


@pytest.mark.parametrize("error", [psycopg.OperationalError, psycopg.ProgrammingError, ValueError])
def test_failure_is_sanitized_and_optional_profile_survives(monkeypatch, caplog, error):
    monkeypatch.setattr(
        "app.integrations.ax_platform.psycopg.connect",
        Mock(side_effect=error("test-secret private database details")),
    )
    service = PlatformService(config())
    assert service.enrich(42).status == "unavailable"
    with pytest.raises(PlatformUnavailable, match="^ax-platform-unavailable$"):
        service.round_teams(42)
    assert "test-secret" not in caplog.text
    assert "test-secret" not in repr(service.config)


def test_disabled_unlinked_missing_and_invalid_row(monkeypatch):
    connect = Mock()
    monkeypatch.setattr("app.integrations.ax_platform.psycopg.connect", connect)
    assert PlatformService(config()).enrich(None).status == "unlinked"
    assert PlatformService(Settings(_env_file=None)).enrich(42).status == "disabled"
    connect.assert_not_called()
    connect.return_value.execute.return_value.fetchone.return_value = None
    assert PlatformService(config()).enrich(42).status == "not_found"
    connect.return_value.execute.return_value.fetchone.return_value = {"team_name": {"bad": 1}}
    assert PlatformService(config()).enrich(42).status == "unavailable"
    assert connect.return_value.close.call_count == 2


@pytest.fixture
def client():
    app = create_app()
    user = User(
        id=7,
        public_id=uuid4(),
        homepage_user_id=42,
        email="game@example.test",
        username="Bridge Name",
        role="STUDENT",
        balance=0,
        mileage=0,
        house_level=1,
        created_at=datetime.now(UTC),
    )
    service = PlatformService(config())
    app.dependency_overrides[resolve_current_user] = lambda: user
    app.dependency_overrides[get_platform_service] = lambda: service
    with TestClient(app) as client:
        yield client, user, service


def test_http_optional_failure_preserves_profile_and_required_history_is_503(client, monkeypatch):
    http, user, service = client
    monkeypatch.setattr(
        service, "_read", Mock(side_effect=PlatformUnavailable("ax-platform-unavailable"))
    )
    response = http.get("/api/v1/session/me")
    assert response.status_code == 200
    assert response.json()["username"] == "Bridge Name"
    assert response.json()["role"] == "STUDENT"
    assert response.json()["platform"] == {"status": "unavailable", "profile": None}
    assert http.get("/api/v1/session/me/round-teams").status_code == 503
    user.homepage_user_id = None
    assert http.get("/api/v1/session/me/round-teams").status_code == 404


def test_http_history_uses_homepage_id_never_game_id_or_supplied_user(client, monkeypatch):
    http, _, service = client
    read = Mock(return_value=[])
    monkeypatch.setattr(service, "_read", read)
    response = http.get("/api/v1/session/me/round-teams?round_id=12&user_id=999")
    assert response.status_code == 200
    read.assert_called_once_with(42, history=True, round_id=12)
    assert http.get("/api/v1/session/me/round-teams?round_id=0").status_code == 422
    assert http.get("/api/v1/session/me/round-teams?round_id=1%20OR%201=1").status_code == 422


def test_unauthenticated_requests_never_read_views(monkeypatch):
    connect = Mock()
    monkeypatch.setattr("app.integrations.ax_platform.psycopg.connect", connect)
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/session/me").status_code == 401
        assert client.get("/api/v1/session/me/round-teams").status_code == 401
    connect.assert_not_called()


def test_profile_image_url_accepts_only_the_configured_student_system(monkeypatch):
    monkeypatch.setattr(settings, "ax_auth_base_url", "https://students.example/app")

    assert _trusted_profile_image_url("/media/avatar.png") == (
        "https://students.example/media/avatar.png"
    )
    assert _trusted_profile_image_url("https://students.example/media/avatar.png") == (
        "https://students.example/media/avatar.png"
    )
    assert _trusted_profile_image_url("https://attacker.example/avatar.png") is None


def test_session_profile_prefers_auth_api_and_keeps_view_team(client):
    _, user, service = client
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    request.state.host_user = HostUser(
        id=42,
        display_name="API Name",
        role="student",
        email="api@example.test",
        profile_image="/media/profiles/api.jpg",
    )
    service.enrich = Mock(
        return_value=PlatformEnrichment(
            status="available",
            profile=PlatformProfile(
                display_name_snapshot="DB Name",
                profile_image="/media/profiles/db.jpg",
                team_name="1조",
            ),
        )
    )

    result = _session_platform_enrichment(request, user, service)

    assert result.status == "available"
    assert result.profile.display_name_snapshot == "API Name"
    assert result.profile.profile_image == "/media/profiles/api.jpg"
    assert result.profile.team_name == "1조"


def test_profile_image_proxy_uses_trusted_url_and_forwards_session_cookie(client, monkeypatch):
    http, _, service = client
    monkeypatch.setattr(settings, "ax_auth_base_url", "https://students.example")
    monkeypatch.setattr(settings, "ax_auth_session_cookie_name", "sessionid")
    monkeypatch.setattr(
        service,
        "enrich",
        Mock(
            return_value=PlatformEnrichment(
                status="available",
                profile=PlatformProfile(profile_image="/media/avatar.png"),
            )
        ),
    )
    requests = []

    class ImageResponse:
        def __init__(self):
            self.headers = {"content-type": "image/png"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b"image-bytes"

    class ImageClient:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        def stream(self, method, url, **kwargs):
            requests.append((method, url, kwargs))
            return ImageResponse()

    monkeypatch.setattr("app.modules.identity.router.httpx.AsyncClient", ImageClient)

    response = http.get("/api/v1/session/me/profile-image", cookies={"sessionid": "secret"})

    assert response.status_code == 200
    assert response.content == b"image-bytes"
    assert response.headers["content-type"] == "image/png"
    assert requests == [
        (
            "GET",
            "https://students.example/media/avatar.png",
            {
                "headers": {"Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif"},
                "cookies": {"sessionid": "secret"},
            },
        )
    ]
