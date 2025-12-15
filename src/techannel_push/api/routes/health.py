"""Health check endpoint."""

from fastapi import APIRouter

from techannel_push import __version__

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": __version__,
    }
