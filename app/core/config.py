from pydantic import SecretStr
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
    grading_output_bytes: int = 65536
    grading_max_concurrency: int = 2
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    def cors_origin_list(self) -> list[str]:
        """Return normalized browser origins accepted by the API."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    sql_grading_database_url: SecretStr | None = None
    sql_grading_connect_timeout_seconds: int = 3
    sql_grading_statement_timeout_ms: int = 1000
    sql_grading_max_rows: int = 1000
    sql_grading_output_bytes: int = 65536

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
