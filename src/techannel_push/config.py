"""Configuration management using pydantic-settings."""

from functools import lru_cache
from typing import Annotated

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_admin_ids(v: str | list[int] | int) -> list[int]:
    """Parse comma-separated admin IDs or return list as-is."""
    if isinstance(v, int):
        return [v]
    if isinstance(v, str):
        return [int(x.strip()) for x in v.split(",") if x.strip()]
    return list(v)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot
    bot_token: str
    webhook_url: str = ""  # Empty = use polling mode
    webhook_secret: str = ""
    use_polling: bool = True  # True for local dev, False for production

    # Admin Configuration
    admin_tg_ids: Annotated[list[int], BeforeValidator(parse_admin_ids)] = []

    # Web API
    api_token: str = "changeme"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/techannel.db"

    # Timezone
    timezone: str = "Asia/Shanghai"

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
