"""Channel group management endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from tgchannel_push.api.deps import ApiAuth, DbSession
from tgchannel_push.database.models import Channel, ChannelGroup, ChannelGroupMember

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupCreate(BaseModel):
    """Group creation model."""

    name: str
    default_slot_count: int = 5


class GroupUpdate(BaseModel):
    """Group update model."""

    name: str | None = None
    default_slot_count: int | None = None


class GroupResponse(BaseModel):
    """Group response model."""

    id: int
    name: str
    default_slot_count: int
    channel_count: int = 0

    class Config:
        from_attributes = True


class GroupMemberAdd(BaseModel):
    """Add channel to group model."""

    channel_ids: list[int]


@router.get("", response_model=list[GroupResponse])
async def list_groups(db: DbSession, _auth: ApiAuth) -> list[dict]:
    """List all channel groups."""
    result = await db.execute(
        select(ChannelGroup).options(selectinload(ChannelGroup.members)).order_by(ChannelGroup.id)
    )
    groups = result.scalars().all()
    return [
        {
            "id": g.id,
            "name": g.name,
            "default_slot_count": g.default_slot_count,
            "channel_count": len(g.members),
        }
        for g in groups
    ]


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(data: GroupCreate, db: DbSession, _auth: ApiAuth) -> dict:
    """Create a new channel group."""
    group = ChannelGroup(name=data.name, default_slot_count=data.default_slot_count)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return {
        "id": group.id,
        "name": group.name,
        "default_slot_count": group.default_slot_count,
        "channel_count": 0,
    }


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(group_id: int, db: DbSession, _auth: ApiAuth) -> dict:
    """Get a specific group."""
    result = await db.execute(
        select(ChannelGroup)
        .where(ChannelGroup.id == group_id)
        .options(selectinload(ChannelGroup.members))
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return {
        "id": group.id,
        "name": group.name,
        "default_slot_count": group.default_slot_count,
        "channel_count": len(group.members),
    }


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(group_id: int, data: GroupUpdate, db: DbSession, _auth: ApiAuth) -> dict:
    """Update a group."""
    result = await db.execute(
        select(ChannelGroup)
        .where(ChannelGroup.id == group_id)
        .options(selectinload(ChannelGroup.members))
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    if data.name is not None:
        group.name = data.name
    if data.default_slot_count is not None:
        group.default_slot_count = data.default_slot_count

    await db.commit()
    return {
        "id": group.id,
        "name": group.name,
        "default_slot_count": group.default_slot_count,
        "channel_count": len(group.members),
    }


@router.delete("/{group_id}")
async def delete_group(group_id: int, db: DbSession, _auth: ApiAuth) -> dict:
    """Delete a group."""
    result = await db.execute(select(ChannelGroup).where(ChannelGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    await db.delete(group)
    await db.commit()
    return {"status": "ok", "message": "Group deleted"}


@router.get("/{group_id}/channels")
async def list_group_channels(group_id: int, db: DbSession, _auth: ApiAuth) -> list[dict]:
    """List channels in a group."""
    result = await db.execute(
        select(Channel)
        .join(ChannelGroupMember, ChannelGroupMember.channel_id == Channel.id)
        .where(ChannelGroupMember.group_id == group_id)
    )
    channels = result.scalars().all()
    return [
        {
            "id": c.id,
            "tg_chat_id": c.tg_chat_id,
            "title": c.title,
            "status": c.status,
        }
        for c in channels
    ]


@router.post("/{group_id}/channels")
async def add_channels_to_group(
    group_id: int, data: GroupMemberAdd, db: DbSession, _auth: ApiAuth
) -> dict:
    """Add channels to a group."""
    # Verify group exists
    result = await db.execute(select(ChannelGroup).where(ChannelGroup.id == group_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    added = 0
    for channel_id in data.channel_ids:
        # Check if already a member
        result = await db.execute(
            select(ChannelGroupMember).where(
                ChannelGroupMember.group_id == group_id,
                ChannelGroupMember.channel_id == channel_id,
            )
        )
        if result.scalar_one_or_none():
            continue

        # Verify channel exists
        result = await db.execute(select(Channel).where(Channel.id == channel_id))
        if not result.scalar_one_or_none():
            continue

        member = ChannelGroupMember(group_id=group_id, channel_id=channel_id)
        db.add(member)
        added += 1

    await db.commit()
    return {"status": "ok", "added": added}


@router.delete("/{group_id}/channels/{channel_id}")
async def remove_channel_from_group(
    group_id: int, channel_id: int, db: DbSession, _auth: ApiAuth
) -> dict:
    """Remove a channel from a group."""
    result = await db.execute(
        select(ChannelGroupMember).where(
            ChannelGroupMember.group_id == group_id,
            ChannelGroupMember.channel_id == channel_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    await db.delete(member)
    await db.commit()
    return {"status": "ok", "message": "Channel removed from group"}
