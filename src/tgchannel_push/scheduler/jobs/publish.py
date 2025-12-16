"""Publish job - executes slot publishing task."""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from tgchannel_push.config import get_settings
from tgchannel_push.database import async_session_maker
from tgchannel_push.database.models import (
    AdCreative,
    Channel,
    ChannelGroup,
    ChannelGroupMember,
    OperationLog,
    Placement,
    Slot,
)
from tgchannel_push.services.publisher import publish_creative_to_channel

logger = logging.getLogger(__name__)
settings = get_settings()


async def execute_slot_publish(slot_id: int) -> None:
    """Execute publishing for a slot.

    This is the main entry point for scheduled publishing tasks.
    """
    logger.info(f"Executing publish for slot {slot_id}")

    async with async_session_maker() as session:
        # Load slot with related data
        result = await session.execute(
            select(Slot)
            .where(Slot.id == slot_id)
            .options(
                selectinload(Slot.group).selectinload(ChannelGroup.members),
                selectinload(Slot.creatives)
            )
        )
        slot = result.scalar_one_or_none()

        if not slot:
            logger.error(f"Slot {slot_id} not found")
            return

        if not slot.enabled:
            logger.info(f"Slot {slot_id} is disabled, skipping")
            return

        # Get enabled creatives for this slot
        creatives = [c for c in slot.creatives if c.enabled]
        if not creatives:
            logger.warning(f"Slot {slot_id} has no enabled creatives")
            return

        # Get channels in the group
        result = await session.execute(
            select(Channel)
            .join(ChannelGroupMember, ChannelGroupMember.channel_id == Channel.id)
            .where(ChannelGroupMember.group_id == slot.group_id)
            .where(Channel.status == "active")
        )
        channels = list(result.scalars().all())

        if not channels:
            logger.warning(f"Slot {slot_id} group has no active channels")
            return

        # Execute based on slot type
        if slot.slot_type == "fixed":
            await execute_fixed_slot(session, slot, creatives[0], channels)
        else:
            await execute_random_slot(session, slot, creatives, channels)

        # Update rotation offset for random slots
        if slot.slot_type == "random":
            slot.rotation_offset = (slot.rotation_offset + 1) % len(creatives)

        await session.commit()


async def execute_fixed_slot(
    session, slot: Slot, creative: AdCreative, channels: list[Channel]
) -> None:
    """Execute publishing for a fixed slot (same creative to all channels)."""
    for channel in channels:
        await publish_to_channel_with_dedup(session, slot, creative, channel)


async def execute_random_slot(
    session, slot: Slot, creatives: list[AdCreative], channels: list[Channel]
) -> None:
    """Execute publishing for a random slot (different creatives to different channels)."""
    import hashlib

    # Generate consistent shuffle based on current cycle
    now = datetime.now(ZoneInfo(settings.timezone))
    cycle_key = f"{now.date()}_{slot.id}"
    seed = int(hashlib.md5(cycle_key.encode()).hexdigest()[:8], 16)

    # Shuffle creatives deterministically
    import random

    rng = random.Random(seed)
    shuffled_creatives = list(creatives)
    rng.shuffle(shuffled_creatives)

    # Assign creatives to channels with deduplication
    for i, channel in enumerate(channels):
        # Try to find a creative not already active in OTHER slots of this channel
        creative = await find_available_creative(
            session, channel.id, slot.id, shuffled_creatives, slot.rotation_offset + i
        )

        if creative:
            await publish_to_channel_with_dedup(session, slot, creative, channel)
        else:
            logger.info(
                f"All creatives already active in channel {channel.id}, skipping"
            )


async def find_available_creative(
    session, channel_id: int, slot_id: int, creatives: list[AdCreative], offset: int
) -> AdCreative | None:
    """Find a creative that is not already active in OTHER slots of the same channel.

    This prevents the same ad from appearing twice in the same channel at the same time,
    but allows replacing the current slot's content.
    """
    # Get all active creative IDs for this channel in OTHER slots
    result = await session.execute(
        select(Placement.creative_id)
        .where(Placement.channel_id == channel_id)
        .where(Placement.slot_id != slot_id)  # Exclude current slot
        .where(Placement.deleted_at.is_(None))
    )
    active_creative_ids = {row[0] for row in result.fetchall() if row[0]}

    # Try each creative in rotation order
    for i in range(len(creatives)):
        candidate = creatives[(offset + i) % len(creatives)]
        if candidate.id not in active_creative_ids:
            return candidate

    return None


async def publish_to_channel_with_dedup(
    session, slot: Slot, creative: AdCreative, channel: Channel
) -> None:
    """Publish a creative to a channel, replacing old message if exists."""
    # Get existing placement for this channel-slot combination
    result = await session.execute(
        select(Placement)
        .where(Placement.channel_id == channel.id)
        .where(Placement.slot_id == slot.id)
    )
    placement = result.scalar_one_or_none()

    # Delete old message if exists (always delete before publishing new one)
    if placement and placement.message_id and placement.deleted_at is None:
        try:
            await delete_old_message(channel.tg_chat_id, placement.message_id)
            logger.info(f"Deleted old message {placement.message_id} from channel {channel.id}")
        except Exception as e:
            logger.warning(f"Failed to delete old message: {e}")
        # Mark as deleted regardless of success (message might already be gone)
        placement.deleted_at = datetime.now(ZoneInfo(settings.timezone))

    # Publish new message
    try:
        message_id = await publish_creative_to_channel(creative, channel)

        now = datetime.now(ZoneInfo(settings.timezone))

        if placement is None:
            placement = Placement(
                channel_id=channel.id,
                slot_id=slot.id,
            )
            session.add(placement)

        placement.creative_id = creative.id
        placement.message_id = message_id
        placement.is_pinned = True
        placement.published_at = now
        placement.deleted_at = None

        # Set scheduled delete time based on slot settings
        if slot.delete_mode == "after_seconds" and slot.delete_after_seconds:
            placement.scheduled_delete_at = now + timedelta(seconds=slot.delete_after_seconds)
        else:
            placement.scheduled_delete_at = None

        # Log success
        log = OperationLog(
            op_type="publish",
            channel_id=channel.id,
            slot_id=slot.id,
            creative_id=creative.id,
            message_id=message_id,
            status="success",
        )
        session.add(log)

        logger.info(f"Published creative {creative.id} to channel {channel.id}")

    except Exception as e:
        # Log failure
        log = OperationLog(
            op_type="publish",
            channel_id=channel.id,
            slot_id=slot.id,
            creative_id=creative.id,
            status="failed",
            error_message=str(e),
        )
        session.add(log)
        logger.error(f"Failed to publish to channel {channel.id}: {e}")


async def delete_old_message(chat_id: int, message_id: int) -> None:
    """Delete an old message from a channel.

    First unpins the message to prevent "Pinned: message deleted" notification residue,
    then deletes the message.
    """
    from tgchannel_push.bot import get_bot
    bot = get_bot()

    # First unpin to avoid "Pinned: message deleted" notification
    try:
        await bot.unpin_chat_message(chat_id=chat_id, message_id=message_id)
        logger.debug(f"Unpinned message {message_id} from {chat_id}")
    except Exception as e:
        # Ignore unpin errors - message might not be pinned or already deleted
        logger.debug(f"Could not unpin message {message_id}: {e}")

    # Then delete the message
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.warning(f"Failed to delete message {message_id} from {chat_id}: {e}")
        raise
