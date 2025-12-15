"""Telegram bot initialization."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from techannel_push.config import get_settings

settings = get_settings()

# Initialize bot with default properties
bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# Initialize dispatcher
dp = Dispatcher()


def setup_handlers() -> None:
    """Register all handlers with the dispatcher."""
    from techannel_push.bot.handlers import channel_events, creative_receiver

    dp.include_router(channel_events.router)
    dp.include_router(creative_receiver.router)
