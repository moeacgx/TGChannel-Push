"""Health check endpoint."""

from fastapi import APIRouter
from sqlalchemy import func, select

from tgchannel_push import __version__
from tgchannel_push.config import get_settings
from tgchannel_push.database import async_session_maker
from tgchannel_push.database.models import AdCreative, Channel

router = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()


@router.get("")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": __version__,
    }


@router.get("/debug")
async def debug_info() -> dict:
    """Debug endpoint to check database status."""
    async with async_session_maker() as session:
        creatives_count = await session.scalar(
            select(func.count()).select_from(AdCreative)
        )
        channels_count = await session.scalar(
            select(func.count()).select_from(Channel)
        )

        # Get latest creative if any
        latest_creative = None
        result = await session.execute(
            select(AdCreative).order_by(AdCreative.created_at.desc()).limit(1)
        )
        creative = result.scalar_one_or_none()
        if creative:
            latest_creative = {
                "id": creative.id,
                "source_chat_id": creative.source_chat_id,
                "caption_preview": creative.caption_preview,
                "created_at": str(creative.created_at) if creative.created_at else None,
            }

    return {
        "status": "ok",
        "version": __version__,
        "database_url": settings.database_url,
        "counts": {
            "creatives": creatives_count or 0,
            "channels": channels_count or 0,
        },
        "latest_creative": latest_creative,
    }
