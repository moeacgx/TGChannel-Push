"""Slot management endpoints."""

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from tgchannel_push.api.deps import ApiAuth, DbSession
from tgchannel_push.config import get_settings
from tgchannel_push.database import async_session_maker
from tgchannel_push.database.models import Channel, ChannelGroup, Placement, Slot
from tgchannel_push.scheduler.scheduler import sync_slot_jobs
from tgchannel_push.services.telegram_utils import delete_message_safe, unpin_message_safe

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/slots", tags=["slots"])


class SlotCreate(BaseModel):
    """Slot creation model."""

    group_id: int
    slot_index: int
    name: str | None = None  # Slot name (optional)
    slot_type: str = "fixed"  # fixed / random
    publish_cron: str
    delete_mode: str = "none"  # none / cron / after_seconds
    delete_cron: str | None = None
    delete_after_seconds: int | None = None


class SlotUpdate(BaseModel):
    """Slot update model."""

    name: str | None = None  # Slot name (optional)
    slot_type: str | None = None
    enabled: bool | None = None
    publish_cron: str | None = None
    delete_mode: str | None = None
    delete_cron: str | None = None
    delete_after_seconds: int | None = None


class SlotResponse(BaseModel):
    """Slot response model."""

    id: int
    group_id: int
    slot_index: int
    name: str | None  # Slot name (optional)
    slot_type: str
    enabled: bool
    publish_cron: str
    delete_mode: str
    delete_cron: str | None
    delete_after_seconds: int | None
    rotation_offset: int

    class Config:
        from_attributes = True


async def clear_slot_messages(db, slot_id: int) -> int:
    """Clear all published messages for a slot from all channels.

    Returns the number of messages cleared.
    Note: This is now a quick database operation. Actual message deletion
    happens in the background via delete_slot_messages_background.
    """
    now = datetime.now(ZoneInfo(settings.timezone))

    # Get all active placements for this slot and mark them as deleted
    result = await db.execute(
        select(Placement)
        .where(Placement.slot_id == slot_id)
        .where(Placement.deleted_at.is_(None))
        .where(Placement.message_id.isnot(None))
    )
    placements = list(result.scalars().all())

    for placement in placements:
        placement.deleted_at = now

    await db.commit()
    return len(placements)


async def delete_slot_messages_background(messages_to_delete: list[tuple[int, int]]) -> None:
    """Background task to delete messages from Telegram with retry.

    Args:
        messages_to_delete: List of (chat_id, message_id) tuples
    """
    from tgchannel_push.bot import get_bot

    try:
        bot = get_bot()
    except Exception as e:
        logger.error(f"Cannot get bot for background deletion: {e}")
        return

    success_count = 0
    fail_count = 0

    for chat_id, message_id in messages_to_delete:
        # Unpin first to avoid notification
        await unpin_message_safe(bot, chat_id, message_id)

        # Delete the message
        if await delete_message_safe(bot, chat_id, message_id):
            success_count += 1
            logger.debug(f"Deleted message {message_id} from chat {chat_id}")
        else:
            fail_count += 1

        # Small delay between operations to avoid rate limiting
        await asyncio.sleep(0.3)

    logger.info(f"Background deletion completed: {success_count} success, {fail_count} failed")


@router.get("", response_model=list[SlotResponse])
async def list_slots(db: DbSession, _auth: ApiAuth, group_id: int | None = None) -> list[Slot]:
    """List all slots, optionally filtered by group."""
    query = select(Slot).order_by(Slot.group_id, Slot.slot_index)
    if group_id is not None:
        query = query.where(Slot.group_id == group_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=SlotResponse, status_code=status.HTTP_201_CREATED)
async def create_slot(data: SlotCreate, db: DbSession, _auth: ApiAuth) -> Slot:
    """Create a new slot."""
    # Verify group exists
    result = await db.execute(select(ChannelGroup).where(ChannelGroup.id == data.group_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    # Check for duplicate slot_index in group
    result = await db.execute(
        select(Slot).where(Slot.group_id == data.group_id, Slot.slot_index == data.slot_index)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slot index {data.slot_index} already exists in this group",
        )

    slot = Slot(
        group_id=data.group_id,
        slot_index=data.slot_index,
        name=data.name,
        slot_type=data.slot_type,
        publish_cron=data.publish_cron,
        delete_mode=data.delete_mode,
        delete_cron=data.delete_cron,
        delete_after_seconds=data.delete_after_seconds,
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)

    # Sync scheduler jobs
    asyncio.create_task(sync_slot_jobs())

    return slot


@router.get("/{slot_id}", response_model=SlotResponse)
async def get_slot(slot_id: int, db: DbSession, _auth: ApiAuth) -> Slot:
    """Get a specific slot."""
    result = await db.execute(select(Slot).where(Slot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
    return slot


@router.put("/{slot_id}", response_model=SlotResponse)
async def update_slot(slot_id: int, data: SlotUpdate, db: DbSession, _auth: ApiAuth) -> Slot:
    """Update a slot."""
    result = await db.execute(select(Slot).where(Slot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")

    if data.name is not None:
        slot.name = data.name
    if data.slot_type is not None:
        slot.slot_type = data.slot_type
    if data.enabled is not None:
        slot.enabled = data.enabled
    if data.publish_cron is not None:
        slot.publish_cron = data.publish_cron
    if data.delete_mode is not None:
        slot.delete_mode = data.delete_mode
    if data.delete_cron is not None:
        slot.delete_cron = data.delete_cron
    if data.delete_after_seconds is not None:
        slot.delete_after_seconds = data.delete_after_seconds

    await db.commit()
    await db.refresh(slot)

    # Sync scheduler jobs
    asyncio.create_task(sync_slot_jobs())

    return slot


@router.delete("/{slot_id}")
async def delete_slot(slot_id: int, db: DbSession, _auth: ApiAuth) -> dict:
    """Delete a slot and schedule background deletion of its published messages."""
    result = await db.execute(select(Slot).where(Slot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")

    # Collect messages to delete BEFORE deleting the slot
    result = await db.execute(
        select(Placement, Channel)
        .join(Channel, Placement.channel_id == Channel.id)
        .where(Placement.slot_id == slot_id)
        .where(Placement.deleted_at.is_(None))
        .where(Placement.message_id.isnot(None))
    )
    messages_to_delete = [
        (channel.tg_chat_id, placement.message_id)
        for placement, channel in result.all()
    ]
    message_count = len(messages_to_delete)

    # Delete the slot (cascades to placements)
    await db.delete(slot)
    await db.commit()

    # Sync scheduler jobs
    asyncio.create_task(sync_slot_jobs())

    # Start background deletion of messages
    if messages_to_delete:
        asyncio.create_task(delete_slot_messages_background(messages_to_delete))
        logger.info(f"Slot {slot_id} deleted, {message_count} messages scheduled for background deletion")

    return {"status": "ok", "message": f"Slot deleted, {message_count} messages being cleaned up in background"}


@router.post("/{slot_id}/enable")
async def enable_slot(slot_id: int, db: DbSession, _auth: ApiAuth) -> dict:
    """Enable a slot."""
    result = await db.execute(select(Slot).where(Slot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")

    slot.enabled = True
    await db.commit()

    # Sync scheduler jobs
    asyncio.create_task(sync_slot_jobs())

    return {"status": "ok", "message": "Slot enabled"}


@router.post("/{slot_id}/disable")
async def disable_slot(slot_id: int, db: DbSession, _auth: ApiAuth) -> dict:
    """Disable (pause) a slot."""
    result = await db.execute(select(Slot).where(Slot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")

    slot.enabled = False
    await db.commit()

    # Sync scheduler jobs
    asyncio.create_task(sync_slot_jobs())

    return {"status": "ok", "message": "Slot disabled"}


@router.post("/{slot_id}/clear")
async def clear_slot(slot_id: int, db: DbSession, _auth: ApiAuth) -> dict:
    """Clear all published messages for a slot without deleting the slot itself.

    This will:
    1. Mark all placements as deleted in database (immediate)
    2. Schedule background deletion of messages from Telegram

    The slot itself remains intact and can continue publishing.
    """
    result = await db.execute(select(Slot).where(Slot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")

    # Collect messages to delete
    result = await db.execute(
        select(Placement, Channel)
        .join(Channel, Placement.channel_id == Channel.id)
        .where(Placement.slot_id == slot_id)
        .where(Placement.deleted_at.is_(None))
        .where(Placement.message_id.isnot(None))
    )
    rows = result.all()
    messages_to_delete = [
        (channel.tg_chat_id, placement.message_id)
        for placement, channel in rows
    ]

    # Mark placements as deleted in database
    now = datetime.now(ZoneInfo(settings.timezone))
    for placement, _channel in rows:
        placement.deleted_at = now
    await db.commit()

    message_count = len(messages_to_delete)

    # Start background deletion of messages
    if messages_to_delete:
        asyncio.create_task(delete_slot_messages_background(messages_to_delete))

    return {"status": "ok", "message": f"{message_count} messages being cleaned up in background"}
