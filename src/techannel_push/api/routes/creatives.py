"""Creative management endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from techannel_push.api.deps import ApiAuth, DbSession
from techannel_push.database.models import AdCreative, Slot

router = APIRouter(prefix="/creatives", tags=["creatives"])


class CreativeUpdate(BaseModel):
    """Creative update model."""

    name: str | None = None  # Creative name (optional)
    slot_id: int | None = None
    enabled: bool | None = None
    caption: str | None = None
    inline_keyboard_json: str | None = None


class CreativeResponse(BaseModel):
    """Creative response model."""

    id: int
    slot_id: int | None
    name: str | None  # Creative name (optional)
    enabled: bool
    source_chat_id: int
    source_message_id: int
    has_media: bool
    media_type: str | None
    media_file_id: str | None
    caption: str | None
    caption_preview: str | None
    inline_keyboard_json: str | None

    class Config:
        from_attributes = True


@router.get("", response_model=list[CreativeResponse])
async def list_creatives(
    db: DbSession, _auth: ApiAuth, slot_id: int | None = None
) -> list[AdCreative]:
    """List all creatives, optionally filtered by slot."""
    query = select(AdCreative).order_by(AdCreative.created_at.desc())
    if slot_id is not None:
        query = query.where(AdCreative.slot_id == slot_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/unbound", response_model=list[CreativeResponse])
async def list_unbound_creatives(db: DbSession, _auth: ApiAuth) -> list[AdCreative]:
    """List creatives not bound to any slot."""
    result = await db.execute(
        select(AdCreative)
        .where(AdCreative.slot_id.is_(None))
        .order_by(AdCreative.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{creative_id}", response_model=CreativeResponse)
async def get_creative(creative_id: int, db: DbSession, _auth: ApiAuth) -> AdCreative:
    """Get a specific creative."""
    result = await db.execute(select(AdCreative).where(AdCreative.id == creative_id))
    creative = result.scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative not found")
    return creative


@router.put("/{creative_id}", response_model=CreativeResponse)
async def update_creative(
    creative_id: int, data: CreativeUpdate, db: DbSession, _auth: ApiAuth
) -> AdCreative:
    """Update a creative."""
    result = await db.execute(select(AdCreative).where(AdCreative.id == creative_id))
    creative = result.scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative not found")

    if data.name is not None:
        creative.name = data.name

    if data.slot_id is not None:
        # Verify slot exists
        result = await db.execute(select(Slot).where(Slot.id == data.slot_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
        creative.slot_id = data.slot_id

    if data.enabled is not None:
        creative.enabled = data.enabled

    if data.caption is not None:
        creative.caption = data.caption
        # Update preview (first 100 chars)
        creative.caption_preview = data.caption[:100] if data.caption else None

    if data.inline_keyboard_json is not None:
        creative.inline_keyboard_json = data.inline_keyboard_json

    await db.commit()
    await db.refresh(creative)
    return creative


@router.post("/{creative_id}/bind/{slot_id}")
async def bind_creative_to_slot(
    creative_id: int, slot_id: int, db: DbSession, _auth: ApiAuth
) -> dict:
    """Bind a creative to a slot."""
    # Verify creative exists
    result = await db.execute(select(AdCreative).where(AdCreative.id == creative_id))
    creative = result.scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative not found")

    # Verify slot exists
    result = await db.execute(select(Slot).where(Slot.id == slot_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")

    creative.slot_id = slot_id
    await db.commit()
    return {"status": "ok", "message": f"Creative {creative_id} bound to slot {slot_id}"}


@router.post("/{creative_id}/unbind")
async def unbind_creative(creative_id: int, db: DbSession, _auth: ApiAuth) -> dict:
    """Unbind a creative from its slot."""
    result = await db.execute(select(AdCreative).where(AdCreative.id == creative_id))
    creative = result.scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative not found")

    creative.slot_id = None
    await db.commit()
    return {"status": "ok", "message": f"Creative {creative_id} unbound"}


@router.delete("/{creative_id}")
async def delete_creative(creative_id: int, db: DbSession, _auth: ApiAuth) -> dict:
    """Delete a creative."""
    result = await db.execute(select(AdCreative).where(AdCreative.id == creative_id))
    creative = result.scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative not found")

    await db.delete(creative)
    await db.commit()
    return {"status": "ok", "message": "Creative deleted"}
