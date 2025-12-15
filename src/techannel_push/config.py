"""Configuration management using pydantic-settings with database fallback."""

import logging
from functools import lru_cache
from typing import Annotated

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def parse_admin_ids(v: str | list[int] | int) -> list[int]:
    """Parse comma-separated admin IDs or return list as-is."""
    if isinstance(v, int):
        return [v]
    if isinstance(v, str):
        if not v.strip():
            return []
        return [int(x.strip()) for x in v.split(",") if x.strip()]
    return list(v)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot - can be empty if configured via database
    bot_token: str = ""
    webhook_url: str = ""  # Empty = use polling mode
    webhook_secret: str = ""
    use_polling: bool = True  # True for local dev, False for production

    # Admin Configuration - can be empty if configured via database
    admin_tg_ids: Annotated[list[int], BeforeValidator(parse_admin_ids)] = []

    # Web API
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


# Database config keys
KEY_BOT_TOKEN = "bot_token"
KEY_ADMIN_TG_IDS = "admin_tg_ids"
KEY_API_PASSWORD_HASH = "api_password_hash"

# Default password for first login
DEFAULT_PASSWORD = "admin123"


def get_db_config_sync(key: str) -> str | None:
    """Get config value from database synchronously (for startup)."""
    import sqlite3
    from pathlib import Path

    settings = get_settings()

    # Extract database path from URL
    db_url = settings.database_url
    if "sqlite" in db_url:
        # sqlite+aiosqlite:///./data/techannel.db -> ./data/techannel.db
        db_path = db_url.split("///")[-1]
        if not Path(db_path).exists():
            return None

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            logger.debug(f"Could not read {key} from database: {e}")
            return None
    return None


def get_effective_bot_token() -> str:
    """Get bot token from .env or database."""
    settings = get_settings()

    # First try .env
    if settings.bot_token:
        return settings.bot_token

    # Then try database
    db_token = get_db_config_sync(KEY_BOT_TOKEN)
    if db_token:
        return db_token

    raise ValueError(
        "Bot token not configured. Please set BOT_TOKEN in .env or configure via Web panel."
    )


def get_effective_admin_ids() -> list[int]:
    """Get admin IDs from .env or database."""
    settings = get_settings()

    # First try .env
    if settings.admin_tg_ids:
        return settings.admin_tg_ids

    # Then try database
    db_ids = get_db_config_sync(KEY_ADMIN_TG_IDS)
    if db_ids:
        return parse_admin_ids(db_ids)

    return []
