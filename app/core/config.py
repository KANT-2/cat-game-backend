from pydantic import Field
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

    def validate_production_secrets(self) -> None:
        """Reject the documented local throttle secret in a production process."""
        if self.app_env == "production" and self.auth_rate_limit_secret == "local-auth-rate-limit-secret":
            raise RuntimeError("AUTH_RATE_LIMIT_SECRET must be configured in production")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
