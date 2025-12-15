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
    slots_router,
)
from techannel_push.bot.bot import bot, dp, setup_handlers
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

    # Start bot (polling or webhook)
    if settings.use_polling:
        # Polling mode - for local development
        logger.info("Starting bot in POLLING mode (local dev)")
        await bot.delete_webhook(drop_pending_updates=True)
        _polling_task = asyncio.create_task(dp.start_polling(bot))
    else:
        # Webhook mode - for production
        webhook_url = settings.webhook_url
        if not webhook_url:
            raise ValueError("WEBHOOK_URL is required when USE_POLLING=false")
        await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret or None,
            drop_pending_updates=True,
        )
        logger.info(f"Webhook set to {webhook_url}")

    # Start scheduler
    start_scheduler()
    await sync_slot_jobs()
    logger.info("Scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    stop_scheduler()

    if settings.use_polling and _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
    else:
        await bot.delete_webhook()

    await bot.session.close()


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
    await dp.feed_update(bot, update)
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
