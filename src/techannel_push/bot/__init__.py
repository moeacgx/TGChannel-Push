"""Bot package."""

from techannel_push.bot.bot import dp

# Note: For 'bot' instance, import directly from bot.bot module
# or use: import techannel_push.bot.bot as bot_module
# then access bot_module.bot to get the current instance
# This is because 'bot' can be reinitialized at runtime (hot-reload)


def get_bot():
    """Get current bot instance (may be None if not initialized)."""
    from techannel_push.bot.bot import bot
    return bot


__all__ = ["dp", "get_bot"]
