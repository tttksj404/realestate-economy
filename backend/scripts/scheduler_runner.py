#!/usr/bin/env python3
import logging
import os
import subprocess
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

ROOT = Path(__file__).resolve().parent.parent
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] scheduler: %(message)s",
)
logger = logging.getLogger("scheduler")


def run_collect_data() -> None:
    source = os.getenv("SCHEDULER_SOURCE", "all")
    months = os.getenv("SCHEDULER_MONTHS", "3")
    cmd = [
        sys.executable,
        "scripts/collect_data.py",
        "--source",
        source,
        "--months",
        str(months),
    ]

    logger.info("Running scheduled data collection: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode != 0:
        logger.error("Scheduled data collection failed with code %s", result.returncode)
    else:
        logger.info("Scheduled data collection completed successfully")


def main() -> None:
    hour = int(os.getenv("SCHEDULER_HOUR", "6"))
    minute = int(os.getenv("SCHEDULER_MINUTE", "0"))
    timezone = os.getenv("SCHEDULER_TIMEZONE", "Asia/Seoul")

    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        run_collect_data,
        CronTrigger(hour=hour, minute=minute, timezone=timezone),
        id="daily_collect_data",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info("Scheduler started (%02d:%02d %s)", hour, minute, timezone)
    scheduler.start()


if __name__ == "__main__":
    main()
