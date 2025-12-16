"""System settings management endpoints."""

import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from tgchannel_push.api.deps import ApiAuth, DbSession, hash_password, get_stored_password_hash
from tgchannel_push.config import DEFAULT_PASSWORD, KEY_API_PASSWORD_HASH
from tgchannel_push.database.models import SystemConfig

router = APIRouter(prefix="/settings", tags=["settings"])
logger = logging.getLogger(__name__)


# Config key constants
KEY_BOT_TOKEN = "bot_token"
KEY_ADMIN_TG_IDS = "admin_tg_ids"


class SettingItem(BaseModel):
    """Single setting item."""

    key: str
    value: str


class SettingsResponse(BaseModel):
    """Settings response model."""

    bot_token: str | None = None
    admin_tg_ids: str | None = None
    bot_configured: bool = False


class BotTokenUpdate(BaseModel):
    """Bot token update model."""

    bot_token: str


class AdminIdsUpdate(BaseModel):
    """Admin IDs update model."""

    admin_tg_ids: str  # Comma-separated list


async def get_config_value(db, key: str) -> str | None:
    """Get a config value from database."""
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    return config.value if config else None


async def set_config_value(db, key: str, value: str) -> None:
    """Set a config value in database."""
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()

    if config:
        config.value = value
    else:
        config = SystemConfig(key=key, value=value)
        db.add(config)

    await db.commit()


@router.get("", response_model=SettingsResponse)
async def get_settings(db: DbSession, _auth: ApiAuth) -> SettingsResponse:
    """Get all system settings."""
    # Import bot module to get current bot instance (may change after hot-reload)
    import tgchannel_push.bot.bot as bot_module

    bot_token = await get_config_value(db, KEY_BOT_TOKEN)
    admin_tg_ids = await get_config_value(db, KEY_ADMIN_TG_IDS)

    return SettingsResponse(
        bot_token=mask_token(bot_token) if bot_token else None,
        admin_tg_ids=admin_tg_ids,
        bot_configured=bot_module.bot is not None,
    )


@router.get("/bot-token/exists")
async def check_bot_token(db: DbSession, _auth: ApiAuth) -> dict:
    """Check if bot token is configured."""
    bot_token = await get_config_value(db, KEY_BOT_TOKEN)
    return {"configured": bool(bot_token)}


@router.put("/bot-token")
async def update_bot_token(data: BotTokenUpdate, db: DbSession, _auth: ApiAuth) -> dict:
    """Update bot token and hot-reload the bot."""
    import asyncio
    import tgchannel_push.bot.bot as bot_module
    from tgchannel_push.bot.bot import dp, reinit_bot
    from tgchannel_push.config import get_settings

    if not data.bot_token or not data.bot_token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot token cannot be empty",
        )

    new_token = data.bot_token.strip()
    settings = get_settings()

    # Save to database first
    await set_config_value(db, KEY_BOT_TOKEN, new_token)
    logger.info("Bot token saved to database")

    # Hot-reload the bot with new token
    try:
        # Get reference to main module's polling task
        import tgchannel_push.main as main_module

        old_bot = bot_module.bot

        # Step 1: Stop old polling task if running
        if settings.use_polling and main_module._polling_task is not None:
            logger.info("Stopping old polling task...")
            main_module._polling_task.cancel()
            try:
                await main_module._polling_task
            except asyncio.CancelledError:
                pass
            main_module._polling_task = None
            logger.info("Old polling task stopped")

        # Step 2: Delete old webhook if in webhook mode
        if old_bot is not None and not settings.use_polling:
            try:
                await old_bot.delete_webhook()
                logger.info("Old webhook deleted")
            except Exception as e:
                logger.warning(f"Error deleting old webhook: {e}")

        # Step 3: Reinitialize bot with new token
        new_bot = await reinit_bot(new_token)
        if new_bot is None:
            logger.error("reinit_bot returned None")
            return {"status": "error", "message": "Failed to initialize bot with new token"}

        logger.info(f"Bot reinitialized: bot_module.bot = {bot_module.bot}")

        # Step 4: Start new polling or set new webhook
        if settings.use_polling:
            logger.info("Starting new polling task...")
            await new_bot.delete_webhook(drop_pending_updates=True)
            main_module._polling_task = asyncio.create_task(dp.start_polling(new_bot))
            logger.info("New polling task started")
        else:
            webhook_url = settings.webhook_url
            if not webhook_url:
                return {"status": "error", "message": "WEBHOOK_URL is required when USE_POLLING=false"}
            await new_bot.set_webhook(
                url=webhook_url,
                secret_token=settings.webhook_secret or None,
                drop_pending_updates=True,
            )
            logger.info(f"New webhook set to {webhook_url}")

        logger.info("Bot hot-reload completed successfully")
        return {"status": "ok", "message": "Bot token updated and bot reloaded successfully"}

    except Exception as e:
        logger.error(f"Failed to hot-reload bot: {e}", exc_info=True)
        return {"status": "warning", "message": f"Token saved but bot reload failed: {str(e)}. Please restart manually."}


@router.put("/admin-ids")
async def update_admin_ids(data: AdminIdsUpdate, db: DbSession, _auth: ApiAuth) -> dict:
    """Update admin Telegram IDs."""
    # Validate format - should be comma-separated integers
    try:
        ids = [int(x.strip()) for x in data.admin_tg_ids.split(",") if x.strip()]
        if not ids:
            raise ValueError("No valid IDs")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid format. Please provide comma-separated Telegram user IDs.",
        )

    await set_config_value(db, KEY_ADMIN_TG_IDS, data.admin_tg_ids.strip())

    return {"status": "ok", "message": "Admin IDs updated successfully"}


def mask_token(token: str) -> str:
    """Mask bot token for display, showing only first and last 4 characters."""
    if len(token) <= 12:
        return "*" * len(token)
    return token[:4] + "*" * (len(token) - 8) + token[-4:]


class PasswordUpdate(BaseModel):
    """Password update model."""

    current_password: str
    new_password: str


class PasswordCheckResponse(BaseModel):
    """Password check response."""

    is_default: bool  # True if using default password


@router.get("/password/status", response_model=PasswordCheckResponse)
async def check_password_status(db: DbSession, _auth: ApiAuth) -> PasswordCheckResponse:
    """Check if user is still using default password."""
    stored_hash = await get_stored_password_hash(db)
    return PasswordCheckResponse(is_default=stored_hash is None)


@router.put("/password")
async def update_password(data: PasswordUpdate, db: DbSession, _auth: ApiAuth) -> dict:
    """Update login password."""
    # Validate new password
    if not data.new_password or len(data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters",
        )

    if data.new_password == data.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    # Verify current password
    stored_hash = await get_stored_password_hash(db)

    if stored_hash:
        # Verify against stored hash
        if hash_password(data.current_password) != stored_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
    else:
        # Verify against default password
        if data.current_password != DEFAULT_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

    # Save new password hash
    new_hash = hash_password(data.new_password)
    await set_config_value(db, KEY_API_PASSWORD_HASH, new_hash)

    logger.info("Password updated successfully")
    return {"status": "ok", "message": "Password updated successfully"}

