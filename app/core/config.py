from urllib.parse import urlsplit

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Cat Game Backend"
    app_env: str = "local"
    database_url: str = "sqlite+pysqlite:///./cat_game.db"
    grading_image: str = "cat-game-python-grader:3.12"
    grading_timeout_seconds: float = 5.0
    grading_memory: str = "128m"
    grading_cpus: float = 0.5
    grading_pids_limit: int = 64
    grading_output_bytes: int = Field(default=65_536, ge=1_024, le=1_048_576)
    grading_max_concurrency: int = 2
    grading_lease_seconds: int = Field(default=60, ge=10, le=3_600)
    grading_poll_seconds: float = Field(default=0.25, ge=0.05, le=10)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    session_days: int = Field(default=30, ge=1, le=365)
    auth_rate_limit_secret: str = Field(default="local-auth-rate-limit-secret", min_length=16)
    auth_rate_window_seconds: int = Field(default=900, ge=60, le=86_400)
    auth_rate_block_seconds: int = Field(default=900, ge=60, le=86_400)
    auth_login_attempt_limit: int = Field(default=5, ge=2, le=100)
    auth_registration_attempt_limit: int = Field(default=10, ge=2, le=1_000)

    def session_cookie_name(self) -> str:
        """Use the browser-enforced host prefix only where HTTPS is mandatory."""
        return "__Host-nyang_session" if self.app_env == "production" else "nyang_session"

    def cors_origin_list(self) -> list[str]:
        """Return normalized browser origins accepted by the API."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    sql_grading_database_url: SecretStr | None = None
    sql_grading_connect_timeout_seconds: int = 3
    sql_grading_statement_timeout_ms: int = 1000
    sql_grading_max_rows: int = 1000
    sql_grading_output_bytes: int = 65536
    ax_auth_base_url: str | None = None
    ax_auth_me_path: str = "/api/auth/me/"
    ax_auth_timeout_seconds: float = 3.0
    ax_auth_session_cookie_name: str = "sessionid"
    ax_platform_database_url: SecretStr | None = None
    ax_platform_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    ax_platform_statement_timeout_ms: int = Field(default=1000, ge=1, le=30_000)
    daily_task_count: int = 3
    daily_reward_balance: int | None = None
    battle_correct_score: int | None = None
    game_timezone: str = "Asia/Seoul"
    gemini_api_key: SecretStr | None = None
    tasks_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.6-flash"
    gemini_timeout_seconds: float = 30.0
    gemini_max_output_tokens: int = 512
    gemini_max_memory_count: int = Field(default=20, ge=1, le=100)

    def validate_production_secrets(self) -> None:
        """Reject the documented local throttle secret in a production process."""
        if self.app_env == "production" and self.auth_rate_limit_secret == "local-auth-rate-limit-secret":
            raise RuntimeError("AUTH_RATE_LIMIT_SECRET must be configured in production")

    def validate_production_api_configuration(self) -> None:
        """Reject storage and browser origins that cannot support production sessions."""
        self.validate_production_secrets()
        if self.app_env != "production":
            return
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise RuntimeError("DATABASE_URL must use PostgreSQL in production")
        origins = self.cors_origin_list()
        if len(origins) != 1 or not _is_https_origin(origins[0]):
            raise RuntimeError("CORS_ORIGINS must contain one HTTPS origin in production")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def _is_https_origin(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
        and parsed.username is None
        and parsed.password is None
    )
