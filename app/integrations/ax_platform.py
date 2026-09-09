"""Read-only AX2 view adapter; never an authentication or authorization provider."""

import logging
from contextlib import closing
from typing import Literal

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)


class PlatformProfile(BaseModel):
    user_email: str | None = None
    primary_email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    display_name_snapshot: str | None = None
    profile_image: str | None = None
    team_name: str | None = None


class RoundTeam(BaseModel):
    round_title: str | None = None
    round_status: str | None = None
    display_name_snapshot: str | None = None
    team_number: int | None = None
    team_name: str | None = None


class PlatformEnrichment(BaseModel):
    status: Literal["available", "disabled", "unlinked", "not_found", "unavailable"]
    profile: PlatformProfile | None = None


class PlatformUnavailable(Exception):
    """Sanitized boundary error: never include a DSN or database exception."""


class PlatformRepository:
    """Only bound SELECTs on the two public views; caller owns the connection."""

    def __init__(self, connection):
        self.connection = connection

    def get_profile(self, user_id: int):
        return self.connection.execute(
            "SELECT user_email, primary_email, first_name, last_name, "
            "display_name_snapshot, profile_image, team_name "
            "FROM public.ax_user_team_login_view WHERE user_id = %s",
            (user_id,),
        ).fetchone()

    def list_round_teams(self, user_id: int, round_id: int | None = None):
        query = (
            "SELECT round_title, round_status, display_name_snapshot, team_number, team_name "
            "FROM public.user_round_team_view WHERE user_id = %s"
        )
        params = (user_id,)
        if round_id is not None:
            query += " AND round_id = %s"
            params = (user_id, round_id)
        query += " ORDER BY round_id, participant_id, team_id NULLS LAST"
        return self.connection.execute(query, params).fetchall()


class PlatformService:
    def __init__(self, config: Settings = settings):
        self.config = config

    def _read(self, user_id: int, *, history: bool = False, round_id: int | None = None):
        secret = self.config.ax_platform_database_url
        if secret is None or not secret.get_secret_value():
            raise PlatformUnavailable("ax-platform-not-configured")
        try:
            dsn = secret.get_secret_value()
            if dsn.startswith("postgresql+psycopg://"):
                dsn = dsn.replace("postgresql+psycopg://", "postgresql://", 1)
            if not dsn.startswith("postgresql://"):
                raise ValueError("unsupported database URL")
            # closing() rolls back by closing, unlike Connection's committing context manager.
            with closing(
                psycopg.connect(
                    dsn,
                    connect_timeout=self.config.ax_platform_connect_timeout_seconds,
                    options=(
                        "-c default_transaction_read_only=on "
                        f"-c statement_timeout={self.config.ax_platform_statement_timeout_ms}"
                    ),
                    row_factory=dict_row,
                )
            ) as connection:
                connection.read_only = True
                repository = PlatformRepository(connection)
                if history:
                    return [
                        RoundTeam.model_validate(row)
                        for row in repository.list_round_teams(user_id, round_id)
                    ]
                row = repository.get_profile(user_id)
                return PlatformProfile.model_validate(row) if row is not None else None
        except (psycopg.Error, ValueError, ValidationError):
            logger.warning("ax-platform-unavailable")
            raise PlatformUnavailable("ax-platform-unavailable") from None

    def enrich(self, homepage_user_id: int | None) -> PlatformEnrichment:
        if homepage_user_id is None:
            return PlatformEnrichment(status="unlinked")
        secret = self.config.ax_platform_database_url
        if secret is None or not secret.get_secret_value():
            return PlatformEnrichment(status="disabled")
        try:
            profile = self._read(homepage_user_id)
        except PlatformUnavailable:
            return PlatformEnrichment(status="unavailable")
        return PlatformEnrichment(
            status="available" if profile is not None else "not_found",
            profile=profile,
        )

    def round_teams(self, homepage_user_id: int, round_id: int | None = None) -> list[RoundTeam]:
        return self._read(homepage_user_id, history=True, round_id=round_id)


def get_platform_service() -> PlatformService:
    return PlatformService()
