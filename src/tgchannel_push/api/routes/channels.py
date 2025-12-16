"""Channel management endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from tgchannel_push.api.deps import ApiAuth, DbSession
from tgchannel_push.database.models import Channel

router = APIRouter(prefix="/channels", tags=["channels"])


class ChannelResponse(BaseModel):
    """Channel response model."""

    id: int
    tg_chat_id: int
    title: str
    username: str | None
    status: str
    permissions_ok: bool

    class Config:
        from_attributes = True


@router.get("", response_model=list[ChannelResponse])
async def list_channels(db: DbSession, _auth: ApiAuth) -> list[Channel]:
    """List all channels."""
    result = await db.execute(select(Channel).order_by(Channel.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(channel_id: int, db: DbSession, _auth: ApiAuth) -> Channel:
    """Get a specific channel."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return channel


@router.delete("/{channel_id}")
async def delete_channel(channel_id: int, db: DbSession, _auth: ApiAuth) -> dict:
    """Delete a channel (mark as left)."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    channel.status = "left"
    await db.commit()
    return {"status": "ok", "message": "Channel marked as left"}
