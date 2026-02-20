"""Background scheduler for automatic pipeline runs.

Uses APScheduler to periodically refresh data from data.gouv.fr.
Activated by setting GOVSENSE_SCHEDULE_INTERVAL (hours) env var.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_last_run: datetime | None = None


def get_last_run() -> datetime | None:
    return _last_run


def _run_pipeline_job():
    """Wrapper executed by the scheduler."""
    global _last_run
    logger.info("Scheduled pipeline run starting ...")
    try:
        from app.pipeline import run_pipeline
        counts = run_pipeline()
        _last_run = datetime.now(timezone.utc)
        logger.info("Scheduled pipeline run complete: %s", counts)
    except Exception:
        logger.exception("Scheduled pipeline run failed")


def start_scheduler() -> bool:
    """Start the background scheduler if configured.

    Returns True if the scheduler was started, False otherwise.
    """
    interval_hours = os.getenv("GOVSENSE_SCHEDULE_INTERVAL")
    if not interval_hours:
        logger.info("Scheduler not configured (set GOVSENSE_SCHEDULE_INTERVAL)")
        return False

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("apscheduler not installed — scheduler disabled")
        return False

    hours = float(interval_hours)
    scheduler = BackgroundScheduler()
    scheduler.add_job(_run_pipeline_job, "interval", hours=hours, id="pipeline_refresh")
    scheduler.start()
    logger.info("Scheduler started — pipeline runs every %.1f hours", hours)
    return True
