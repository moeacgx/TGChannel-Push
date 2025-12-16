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
from tgchannel_push.database.models import Channel, ChannelGroup, Placement, Slot
from tgchannel_push.scheduler.scheduler import sync_slot_jobs

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
    """
    from tgchannel_push.bot import get_bot
    bot = get_bot()

    # Get all active placements for this slot
    result = await db.execute(
        select(Placement, Channel)
        .join(Channel, Placement.channel_id == Channel.id)
        .where(Placement.slot_id == slot_id)
        .where(Placement.deleted_at.is_(None))
        .where(Placement.message_id.isnot(None))
    )
    placements = result.all()

    cleared_count = 0
    now = datetime.now(ZoneInfo(settings.timezone))

    for placement, channel in placements:
        try:
            # First unpin to avoid "Pinned: message deleted" notification
            try:
                await bot.unpin_chat_message(
                    chat_id=channel.tg_chat_id, message_id=placement.message_id
                )
                logger.debug(f"Unpinned message {placement.message_id} from channel {channel.id}")
            except Exception as e:
                logger.debug(f"Could not unpin message {placement.message_id}: {e}")

            # Then delete the message
            await bot.delete_message(
                chat_id=channel.tg_chat_id, message_id=placement.message_id
            )
            logger.info(f"Deleted message {placement.message_id} from channel {channel.id}")
            cleared_count += 1
        except Exception as e:
            logger.warning(f"Failed to delete message {placement.message_id}: {e}")

        # Mark placement as deleted regardless of success
        placement.deleted_at = now

    await db.commit()
    return cleared_count


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
    """Delete a slot and clear all its published messages."""
    result = await db.execute(select(Slot).where(Slot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")

    # Clear all published messages for this slot
    cleared_count = await clear_slot_messages(db, slot_id)
    logger.info(f"Cleared {cleared_count} messages for slot {slot_id}")

    await db.delete(slot)
    await db.commit()

    # Sync scheduler jobs
    asyncio.create_task(sync_slot_jobs())

    return {"status": "ok", "message": f"Slot deleted, {cleared_count} messages cleared"}


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
    1. Unpin all pinned messages from this slot in all channels
    2. Delete all messages from this slot in all channels
    3. Mark all placements as deleted

    The slot itself remains intact and can continue publishing.
    """
    result = await db.execute(select(Slot).where(Slot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")

    cleared_count = await clear_slot_messages(db, slot_id)

    return {"status": "ok", "message": f"{cleared_count} messages cleared"}
