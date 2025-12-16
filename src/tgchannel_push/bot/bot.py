"""Telegram bot initialization."""

import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from tgchannel_push.config import get_effective_bot_token

logger = logging.getLogger(__name__)

# Initialize dispatcher (always available)
dp = Dispatcher()

# Initialize bot - may be None if token not configured
bot: Bot | None = None


def init_bot() -> Bot | None:
    """Initialize bot with token. Returns None if token not configured."""
    global bot
    try:
        token = get_effective_bot_token()
        if not token:
            logger.warning("Bot not initialized: token not configured")
            return None
        bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        logger.info("Bot initialized successfully")
        return bot
    except Exception as e:
        logger.warning(f"Bot not initialized: {e}")
        return None


async def reinit_bot(new_token: str) -> Bot | None:
    """Reinitialize bot with a new token. Closes old bot session if exists.

    Args:
        new_token: The new bot token to use

    Returns:
        The new Bot instance or None if initialization failed
    """
    global bot

    # Close old bot session if exists
    if bot is not None:
        try:
            await bot.session.close()
            logger.info("Old bot session closed")
        except Exception as e:
            logger.warning(f"Error closing old bot session: {e}")

    # Create new bot instance
    try:
        bot = Bot(
            token=new_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        logger.info("Bot reinitialized with new token")
        return bot
    except Exception as e:
        logger.error(f"Failed to reinitialize bot: {e}")
        bot = None
        return None


# Try to initialize on import
init_bot()


def setup_handlers() -> None:
    """Register all handlers with the dispatcher."""
    from tgchannel_push.bot.handlers import channel_events, creative_receiver

    dp.include_router(channel_events.router)
    dp.include_router(creative_receiver.router)
