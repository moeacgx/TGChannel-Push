"""Publisher service - handles message publishing to channels."""

import asyncio
import json
import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from tgchannel_push.database.models import AdCreative, Channel

logger = logging.getLogger(__name__)


def _build_reply_markup(creative: AdCreative) -> InlineKeyboardMarkup | None:
    """Build inline keyboard from creative's JSON config."""
    if not creative.inline_keyboard_json:
        return None

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
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    except Exception as e:
        logger.warning(f"Failed to parse inline keyboard: {e}")
        return None


async def publish_creative_to_channel(creative: AdCreative, channel: Channel) -> int:
    """Publish a creative to a channel.

    If the creative has media_file_id, use send_photo/send_video etc. with the edited caption.
    Otherwise, fall back to copy_message for the original format.

    Args:
        creative: The ad creative to publish
        channel: The target channel

    Returns:
        The message_id of the published message
    """
    from tgchannel_push.bot import get_bot
    bot = get_bot()

    reply_markup = _build_reply_markup(creative)
    caption = creative.caption or ""

    # If we have media_file_id, send using the appropriate method with edited caption
    if creative.media_file_id and creative.media_type:
        message_id = await _send_media_message(
            bot, channel.tg_chat_id, creative, caption, reply_markup
        )
    elif creative.has_media:
        # Has media but no file_id saved, fall back to copy_message
        # (This is for backward compatibility with old records)
        result = await bot.copy_message(
            chat_id=channel.tg_chat_id,
            from_chat_id=creative.source_chat_id,
            message_id=creative.source_message_id,
            caption=caption if caption else None,
            reply_markup=reply_markup,
        )
        message_id = result.message_id
    else:
        # Text-only message
        if caption:
            result = await bot.send_message(
                chat_id=channel.tg_chat_id,
                text=caption,
                reply_markup=reply_markup,
            )
            message_id = result.message_id
        else:
            # No caption, no media - just copy the original
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
        await asyncio.sleep(0.5)
        await _try_delete_pin_service_message(bot, channel.tg_chat_id, message_id + 1)

    except Exception as e:
        logger.warning(f"Failed to pin message: {e}")

    return message_id


async def _send_media_message(
    bot, chat_id: int, creative: AdCreative, caption: str, reply_markup
) -> int:
    """Send media message using the appropriate method based on media_type."""
    media_type = creative.media_type
    file_id = creative.media_file_id

    if media_type == "photo":
        result = await bot.send_photo(
            chat_id=chat_id,
            photo=file_id,
            caption=caption or None,
            reply_markup=reply_markup,
        )
    elif media_type == "video":
        result = await bot.send_video(
            chat_id=chat_id,
            video=file_id,
            caption=caption or None,
            reply_markup=reply_markup,
        )
    elif media_type == "animation":
        result = await bot.send_animation(
            chat_id=chat_id,
            animation=file_id,
            caption=caption or None,
            reply_markup=reply_markup,
        )
    elif media_type == "document":
        result = await bot.send_document(
            chat_id=chat_id,
            document=file_id,
            caption=caption or None,
            reply_markup=reply_markup,
        )
    else:
        # Unknown media type, try copy_message as fallback
        result = await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=creative.source_chat_id,
            message_id=creative.source_message_id,
            caption=caption or None,
            reply_markup=reply_markup,
        )

    return result.message_id


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
