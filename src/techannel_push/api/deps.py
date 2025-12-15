"""API dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from techannel_push.config import get_settings
from techannel_push.database import async_session_maker

settings = get_settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def verify_api_token(x_api_token: Annotated[str | None, Header()] = None) -> str:
    """Verify API token from header."""
    if x_api_token != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )
    return x_api_token


# Type aliases for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]
ApiAuth = Annotated[str, Depends(verify_api_token)]
