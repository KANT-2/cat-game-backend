import pytest

from app.core.config import Settings


def test_migration_database_url_preserves_explicit_alembic_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)

    assert (
        settings.resolve_migration_database_url("postgresql+psycopg://postgres@localhost/cat_game")
        == "postgresql+psycopg://postgres@localhost/cat_game"
    )


def test_migration_database_url_prefers_explicit_runtime_setting() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://runtime@database/cat_game",
    )

    assert (
        settings.resolve_migration_database_url("postgresql+psycopg://ini@localhost/cat_game")
        == "postgresql+psycopg://runtime@database/cat_game"
    )


def test_migration_database_url_falls_back_when_alembic_url_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)

    assert settings.resolve_migration_database_url(None) == "sqlite+pysqlite:///./cat_game.db"
