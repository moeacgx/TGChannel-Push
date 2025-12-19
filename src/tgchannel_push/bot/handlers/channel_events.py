"""Handler for channel join/leave events."""

import logging

from aiogram import F, Router
from aiogram.types import ChatMemberUpdated

from tgchannel_push.config import get_settings
from tgchannel_push.database import async_session_maker
from tgchannel_push.database.models import Channel

logger = logging.getLogger(__name__)
settings = get_settings()

router = Router(name="channel_events")


@router.my_chat_member(F.chat.type == "channel")
async def on_bot_channel_status_change(event: ChatMemberUpdated) -> None:
    """Handle bot being added to or removed from a channel."""
    chat = event.chat
    new_status = event.new_chat_member.status

    async with async_session_maker() as session:
        # Check if channel already exists
        from sqlalchemy import select

        result = await session.execute(select(Channel).where(Channel.tg_chat_id == chat.id))
        channel = result.scalar_one_or_none()

        if new_status in ("administrator", "member"):
            permissions_ok = False
            if new_status == "administrator":
                permissions_ok = True
                required_flags = ("can_post_messages", "can_delete_messages", "can_pin_messages")
                missing_flags = []
                for flag in required_flags:
                    value = getattr(event.new_chat_member, flag, None)
                    if value is False:
                        missing_flags.append(flag)
                        permissions_ok = False
                if missing_flags:
                    logger.warning(
                        f"Bot is administrator in channel {chat.id} but missing permissions: {missing_flags}"
                    )

            # Bot was added to channel
            if channel is None:
                channel = Channel(
                    tg_chat_id=chat.id,
                    title=chat.title or "Unknown",
                    username=chat.username,
                    status="active",
                    permissions_ok=permissions_ok,
                )
                session.add(channel)
                logger.info(f"Bot added to channel: {chat.title} ({chat.id})")
            else:
                channel.title = chat.title or channel.title
                channel.username = chat.username
                channel.status = "active"
                channel.permissions_ok = permissions_ok
                logger.info(f"Bot status updated in channel: {chat.title} ({chat.id})")

        elif new_status in ("left", "kicked"):
            # Bot was removed from channel
            if channel is not None:
                channel.status = "left"
                channel.permissions_ok = False
                logger.info(f"Bot removed from channel: {chat.title} ({chat.id})")

        await session.commit()
