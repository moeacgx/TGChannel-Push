"""APScheduler configuration."""

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from tgchannel_push.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Create scheduler with Beijing timezone
scheduler = AsyncIOScheduler(
    timezone=ZoneInfo(settings.timezone),
)


def parse_cron(cron_expr: str) -> CronTrigger:
    """Parse a cron expression into an APScheduler trigger.

    Args:
        cron_expr: Cron expression (5 fields: minute hour day month day_of_week)

    Returns:
        CronTrigger configured with the cron expression
    """
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr}")

    return CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
        timezone=ZoneInfo(settings.timezone),
    )


async def sync_slot_jobs() -> None:
    """Synchronize scheduler jobs with database slots.

    This should be called on startup and whenever slots are modified.
    """
    from tgchannel_push.database import async_session_maker
    from tgchannel_push.database.models import Slot
    from tgchannel_push.scheduler.jobs.publish import execute_slot_publish

    from sqlalchemy import select

    # Remove all existing slot jobs
    for job in scheduler.get_jobs():
        if job.id.startswith("slot_"):
            scheduler.remove_job(job.id)

    # Add jobs for enabled slots
    async with async_session_maker() as session:
        result = await session.execute(select(Slot).where(Slot.enabled == True))  # noqa: E712
        slots = result.scalars().all()

        for slot in slots:
            job_id = f"slot_{slot.id}_publish"
            try:
                trigger = parse_cron(slot.publish_cron)
                scheduler.add_job(
                    execute_slot_publish,
                    trigger=trigger,
                    id=job_id,
                    args=[slot.id],
                    replace_existing=True,
                )
                logger.info(f"Added publish job for slot {slot.id}: {slot.publish_cron}")
            except Exception as e:
                logger.error(f"Failed to add job for slot {slot.id}: {e}")


def start_scheduler() -> None:
    """Start the scheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler() -> None:
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
