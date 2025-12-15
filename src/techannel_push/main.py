"""Main application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import types
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from techannel_push import __version__
from techannel_push.api.routes import (
    channels_router,
    creatives_router,
    groups_router,
    health_router,
    settings_router,
    slots_router,
)
import techannel_push.bot.bot as bot_module
from techannel_push.bot.bot import dp, setup_handlers, reinit_bot
from techannel_push.config import get_settings
from techannel_push.database import init_db
from techannel_push.scheduler.scheduler import start_scheduler, stop_scheduler, sync_slot_jobs

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global polling task reference
_polling_task: asyncio.Task | None = None


async def restart_bot_with_token(new_token: str) -> dict:
    """Hot-reload bot with a new token without restarting the entire service.

    This function:
    1. Stops the current polling task (if running)
    2. Deletes the old webhook (if in webhook mode)
    3. Reinitializes the bot with the new token
    4. Restarts polling or sets new webhook

    Args:
        new_token: The new bot token

    Returns:
        dict with status and message
    """
    global _polling_task

    import techannel_push.bot.bot as bot_module

    old_bot = bot_module.bot
    logger.info("Starting bot hot-reload...")

    # Step 1: Stop old polling task if running
    if settings.use_polling and _polling_task is not None:
        logger.info("Stopping old polling task...")
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
        _polling_task = None
        logger.info("Old polling task stopped")

    # Step 2: Delete old webhook if in webhook mode
    if old_bot is not None and not settings.use_polling:
        try:
            await old_bot.delete_webhook()
            logger.info("Old webhook deleted")
        except Exception as e:
            logger.warning(f"Error deleting old webhook: {e}")

    # Step 3: Reinitialize bot with new token
    new_bot = await reinit_bot(new_token)
    if new_bot is None:
        return {"status": "error", "message": "Failed to initialize bot with new token"}

    # Step 4: Start new polling or set new webhook
    if settings.use_polling:
        logger.info("Starting new polling task...")
        await new_bot.delete_webhook(drop_pending_updates=True)
        _polling_task = asyncio.create_task(dp.start_polling(new_bot))
        logger.info("New polling task started")
    else:
        webhook_url = settings.webhook_url
        if not webhook_url:
            return {"status": "error", "message": "WEBHOOK_URL is required when USE_POLLING=false"}
        await new_bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret or None,
            drop_pending_updates=True,
        )
        logger.info(f"New webhook set to {webhook_url}")

    logger.info("Bot hot-reload completed successfully")
    return {"status": "ok", "message": "Bot reloaded with new token successfully"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global _polling_task

    # Startup
    logger.info(f"Starting TeChannel-Push v{__version__}")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Setup bot handlers
    setup_handlers()

    # Start bot only if token is configured
    if bot_module.bot is not None:
        if settings.use_polling:
            # Polling mode - for local development
            logger.info("Starting bot in POLLING mode (local dev)")
            await bot_module.bot.delete_webhook(drop_pending_updates=True)
            _polling_task = asyncio.create_task(dp.start_polling(bot_module.bot))
        else:
            # Webhook mode - for production
            webhook_url = settings.webhook_url
            if not webhook_url:
                raise ValueError("WEBHOOK_URL is required when USE_POLLING=false")
            await bot_module.bot.set_webhook(
                url=webhook_url,
                secret_token=settings.webhook_secret or None,
                drop_pending_updates=True,
            )
            logger.info(f"Webhook set to {webhook_url}")
    else:
        logger.warning("Bot not started - token not configured. Configure via Web panel and restart.")

    # Start scheduler
    start_scheduler()
    await sync_slot_jobs()
    logger.info("Scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    stop_scheduler()

    if bot_module.bot is not None:
        if settings.use_polling and _polling_task:
            _polling_task.cancel()
            try:
                await _polling_task
            except asyncio.CancelledError:
                pass
        else:
            await bot_module.bot.delete_webhook()

        await bot_module.bot.session.close()


# Create FastAPI app
app = FastAPI(
    title="TeChannel-Push",
    description="Telegram Multi-Channel Ad Pinning Bot",
    version=__version__,
    lifespan=lifespan,
)

# Add CORS middleware (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(health_router, prefix="/api")
app.include_router(channels_router, prefix="/api")
app.include_router(groups_router, prefix="/api")
app.include_router(slots_router, prefix="/api")
app.include_router(creatives_router, prefix="/api")
app.include_router(settings_router, prefix="/api")

# Static files for web frontend
# Determine the web dist directory path
_web_dist_dir = Path(__file__).parent.parent.parent / "web" / "dist"

# Mount static assets if the dist directory exists
if _web_dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=_web_dist_dir / "assets"), name="assets")

    @app.get("/")
    async def serve_index():
        """Serve the Vue SPA index page."""
        return FileResponse(_web_dist_dir / "index.html")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Fallback route for SPA - serve index.html for client-side routing."""
        # Skip API routes and webhook
        if full_path.startswith("api/") or full_path == "webhook":
            return {"error": "Not found"}

        # Check if it's a static file
        file_path = _web_dist_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        # Otherwise serve index.html for SPA routing
        return FileResponse(_web_dist_dir / "index.html")
else:
    @app.get("/")
    async def no_frontend():
        """Placeholder when frontend is not built."""
        return {
            "message": "TeChannel-Push API Server",
            "version": __version__,
            "docs": "/docs",
            "note": "Frontend not built. Run 'cd web && npm install && npm run build' to enable web panel."
        }


@app.post("/webhook")
async def webhook_handler(request: Request) -> dict:
    """Handle incoming Telegram updates via webhook."""
    # Check if bot is configured
    if bot_module.bot is None:
        return {"ok": False, "error": "Bot not configured"}

    # Only process if in webhook mode
    if settings.use_polling:
        return {"ok": False, "error": "Webhook disabled in polling mode"}

    # Verify secret token if configured
    if settings.webhook_secret:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != settings.webhook_secret:
            logger.warning("Invalid webhook secret token")
            return {"ok": False}

    # Parse and process update
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot_module.bot, update)
    return {"ok": True}


def main() -> None:
    """Run the application."""
    import uvicorn

    uvicorn.run(
        "techannel_push.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
