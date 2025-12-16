"""Publisher service - handles message publishing to channels."""

import asyncio
import json
import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from tgchannel_push.database.models import AdCreative, Channel

logger = logging.getLogger(__name__)


async def publish_creative_to_channel(creative: AdCreative, channel: Channel) -> int:
    """Publish a creative to a channel.

    This uses copyMessage to preserve the original message format without
    showing "Forwarded from" attribution.

    Args:
        creative: The ad creative to publish
        channel: The target channel

    Returns:
        The message_id of the published message
    """
    from tgchannel_push.bot import get_bot
    bot = get_bot()

    # Build inline keyboard if specified
    reply_markup = None
    if creative.inline_keyboard_json:
        try:
            keyboard_data = json.loads(creative.inline_keyboard_json)
            buttons = []
            for row in keyboard_data:
                row_buttons = []
                for btn in row:
                    if "url" in btn:
                        row_buttons.append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
                    elif "callback_data" in btn:
                        row_buttons.append(
                            InlineKeyboardButton(
                                text=btn["text"], callback_data=btn["callback_data"]
                            )
                        )
                buttons.append(row_buttons)
            reply_markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        except Exception as e:
            logger.warning(f"Failed to parse inline keyboard: {e}")

    # Copy message to channel
    result = await bot.copy_message(
        chat_id=channel.tg_chat_id,
        from_chat_id=creative.source_chat_id,
        message_id=creative.source_message_id,
        reply_markup=reply_markup,
    )

    message_id = result.message_id

    # Pin the message
    try:
        await bot.pin_chat_message(
            chat_id=channel.tg_chat_id,
            message_id=message_id,
            disable_notification=True,
        )

        # Try to delete the "pinned message" service notification
        # The service message ID is usually the pinned message ID + 1
        await asyncio.sleep(0.5)  # Small delay to ensure service message is created
        await _try_delete_pin_service_message(bot, channel.tg_chat_id, message_id + 1)

    except Exception as e:
        logger.warning(f"Failed to pin message: {e}")

    return message_id


async def _try_delete_pin_service_message(bot, chat_id: int, message_id: int) -> None:
    """Try to delete the pin service message safely.

    Uses copy_message to verify the message is a service message (not a regular message).
    Service messages cannot be copied, so if copy succeeds, it's a regular message
    and we should NOT delete it.
    """
    try:
        # Try to copy the message - service messages cannot be copied
        copied = await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=chat_id,
            message_id=message_id,
        )
        # Copy succeeded - this is a regular message, delete the copy and keep original
        await bot.delete_message(chat_id=chat_id, message_id=copied.message_id)
        logger.debug(f"Message {message_id} is a regular message, not deleting")
    except Exception:
        # Copy failed - likely a service message or doesn't exist, try to delete
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.debug(f"Deleted pin service message {message_id}")
        except Exception:
            # Message doesn't exist or can't be deleted, ignore
            pass


async def unpin_message(channel: Channel, message_id: int) -> None:
    """Unpin a message in a channel.

    Args:
        channel: The channel
        message_id: The message to unpin
    """
    from tgchannel_push.bot import get_bot
    bot = get_bot()

    try:
        await bot.unpin_chat_message(chat_id=channel.tg_chat_id, message_id=message_id)
    except Exception as e:
        logger.warning(f"Failed to unpin message {message_id}: {e}")


async def delete_message(channel: Channel, message_id: int) -> None:
    """Delete a message from a channel.

    Args:
        channel: The channel
        message_id: The message to delete
    """
    from tgchannel_push.bot import get_bot
    bot = get_bot()

    try:
        await bot.delete_message(chat_id=channel.tg_chat_id, message_id=message_id)
    except Exception as e:
        logger.warning(f"Failed to delete message {message_id}: {e}")
        raise
