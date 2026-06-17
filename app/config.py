from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Turso (libSQL) — remoto: URL + token; local: omita e use arquivo em turso_local_database_path
    turso_database_url: str = Field(
        default="",
        validation_alias=AliasChoices("TURSO_DATABASE_URL", "DATABASE_URL"),
    )
    turso_auth_token: str = Field(default="", validation_alias="TURSO_AUTH_TOKEN")
    turso_local_database_path: str = Field(
        default="sqlite+libsql:///rastro.db",
        validation_alias=AliasChoices("TURSO_LOCAL_DATABASE_PATH"),
    )

    # Auth
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 30

    anthropic_api_key: str = ""

    app_name: str = "Rastro API"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
