from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Cat Game Backend"
    app_env: str = "local"
    database_url: str = "sqlite+pysqlite:///./cat_game.db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
