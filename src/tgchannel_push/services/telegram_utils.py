"""Telegram API utilities with retry and rate limiting handling."""

import asyncio
import logging
from typing import Any, Callable, Coroutine

from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError

logger = logging.getLogger(__name__)

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds


async def with_retry(
    func: Callable[..., Coroutine[Any, Any, Any]],
    *args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    **kwargs,
) -> Any:
    """Execute a Telegram API call with automatic retry on rate limiting.

    Handles FloodWait (TelegramRetryAfter) by waiting the specified time.
    Retries on other transient errors with exponential backoff.

    Args:
        func: The async function to call
        *args: Positional arguments for the function
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries (doubles each retry)
        **kwargs: Keyword arguments for the function

    Returns:
        The result of the function call

    Raises:
        The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except TelegramRetryAfter as e:
            # FloodWait - wait the specified time
            wait_time = e.retry_after + 1  # Add 1 second buffer
            logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries + 1})")
            await asyncio.sleep(wait_time)
            last_exception = e
        except TelegramAPIError as e:
            # Other Telegram errors - check if retryable
            error_str = str(e).lower()
            if any(x in error_str for x in ["timeout", "connection", "network"]):
                # Transient error - retry with backoff
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Transient error: {e}, retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})")
                await asyncio.sleep(delay)
                last_exception = e
            else:
                # Non-retryable error (e.g., chat not found, no permission)
                raise
        except Exception as e:
            # Unexpected error - don't retry
            raise

    # All retries exhausted
    if last_exception:
        raise last_exception


async def delete_message_safe(bot, chat_id: int, message_id: int) -> bool:
    """Delete a message with retry, returns True if successful or message already gone."""
    try:
        await with_retry(bot.delete_message, chat_id=chat_id, message_id=message_id)
        return True
    except TelegramAPIError as e:
        error_str = str(e).lower()
        if "message to delete not found" in error_str or "message can't be deleted" in error_str:
            # Message already deleted or too old
            logger.debug(f"Message {message_id} already deleted or not found")
            return True
        logger.warning(f"Failed to delete message {message_id}: {e}")
        return False


async def unpin_message_safe(bot, chat_id: int, message_id: int) -> bool:
    """Unpin a message with retry, returns True if successful or message not pinned."""
    try:
        await with_retry(bot.unpin_chat_message, chat_id=chat_id, message_id=message_id)
        return True
    except TelegramAPIError as e:
        # Ignore unpin errors - message might not be pinned
        logger.debug(f"Could not unpin message {message_id}: {e}")
        return False


async def send_message_safe(bot, chat_id: int, **kwargs) -> Any:
    """Send a message with retry."""
    return await with_retry(bot.send_message, chat_id=chat_id, **kwargs)


async def send_photo_safe(bot, chat_id: int, **kwargs) -> Any:
    """Send a photo with retry."""
    return await with_retry(bot.send_photo, chat_id=chat_id, **kwargs)


async def send_video_safe(bot, chat_id: int, **kwargs) -> Any:
    """Send a video with retry."""
    return await with_retry(bot.send_video, chat_id=chat_id, **kwargs)


async def send_animation_safe(bot, chat_id: int, **kwargs) -> Any:
    """Send an animation with retry."""
    return await with_retry(bot.send_animation, chat_id=chat_id, **kwargs)


async def send_document_safe(bot, chat_id: int, **kwargs) -> Any:
    """Send a document with retry."""
    return await with_retry(bot.send_document, chat_id=chat_id, **kwargs)


async def copy_message_safe(bot, chat_id: int, **kwargs) -> Any:
    """Copy a message with retry."""
    return await with_retry(bot.copy_message, chat_id=chat_id, **kwargs)


async def pin_message_safe(bot, chat_id: int, message_id: int, disable_notification: bool = True) -> bool:
    """Pin a message with retry."""
    try:
        await with_retry(
            bot.pin_chat_message,
            chat_id=chat_id,
            message_id=message_id,
            disable_notification=disable_notification,
        )
        return True
    except TelegramAPIError as e:
        logger.warning(f"Failed to pin message {message_id}: {e}")
        return False
