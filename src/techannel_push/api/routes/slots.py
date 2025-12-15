"""Slot management endpoints."""

import asyncio
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from techannel_push.api.deps import ApiAuth, DbSession
from techannel_push.database.models import ChannelGroup, Slot
from techannel_push.scheduler.scheduler import sync_slot_jobs

router = APIRouter(prefix="/slots", tags=["slots"])


class SlotCreate(BaseModel):
    """Slot creation model."""

    group_id: int
    slot_index: int
    slot_type: str = "fixed"  # fixed / random
    publish_cron: str
    delete_mode: str = "none"  # none / cron / after_seconds
    delete_cron: str | None = None
    delete_after_seconds: int | None = None


class SlotUpdate(BaseModel):
    """Slot update model."""

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
    slot_type: str
    enabled: bool
    publish_cron: str
    delete_mode: str
    delete_cron: str | None
    delete_after_seconds: int | None
    rotation_offset: int

    class Config:
        from_attributes = True


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
    """Delete a slot."""
    result = await db.execute(select(Slot).where(Slot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")

    await db.delete(slot)
    await db.commit()

    # Sync scheduler jobs
    asyncio.create_task(sync_slot_jobs())

    return {"status": "ok", "message": "Slot deleted"}


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
