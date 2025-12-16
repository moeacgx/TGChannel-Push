"""API dependencies."""

import hashlib
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tgchannel_push.config import DEFAULT_PASSWORD, KEY_API_PASSWORD_HASH, get_settings
from tgchannel_push.database import async_session_maker
from tgchannel_push.database.models import SystemConfig

settings = get_settings()


def hash_password(password: str) -> str:
    """Hash password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(plain_password) == hashed_password


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_stored_password_hash(db: AsyncSession) -> str | None:
    """Get stored password hash from database."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == KEY_API_PASSWORD_HASH)
    )
    config = result.scalar_one_or_none()
    return config.value if config else None


async def verify_api_token(
    x_api_token: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> str:
    """Verify API token (password) from header."""
    if not x_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API token",
        )

    # Get stored password hash from database
    stored_hash = await get_stored_password_hash(db)

    if stored_hash:
        # Verify against stored hash
        if not verify_password(x_api_token, stored_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API token",
            )
    else:
        # No password set, verify against default password
        if x_api_token != DEFAULT_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API token",
            )

    return x_api_token


# Type aliases for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]
ApiAuth = Annotated[str, Depends(verify_api_token)]
