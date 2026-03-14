"""
scheduler.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Energy API — APScheduler Background Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scheduled tasks for:
- Daily CCEI HFED data extraction
- Daily weather data extraction
- Daily model retraining
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import subprocess
import logging
from datetime import datetime
from pathlib import Path

from .config import settings, get_project_root

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler()


# ── Scheduled Tasks ───────────────────────────────────────────────────────────

def run_ccei_extraction():
    """
    Daily task: Extract NS load data from CCEI HFED.

    Runs at time specified in settings.ccei_poll_time (default: 06:00)
    """
    logger.info("Starting scheduled CCEI HFED extraction...")

    try:
        script_path = get_project_root() / "scripts" / "nsp_extract.py"

        if not script_path.exists():
            logger.error(f"nsp_extract.py not found: {script_path}")
            return

        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5-minute timeout
        )

        if result.returncode == 0:
            logger.info("  ✓ CCEI extraction completed successfully")
            logger.info(f"  Output: {result.stdout[:200]}")
        else:
            logger.error(f"  ✗ CCEI extraction failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        logger.error("  ✗ CCEI extraction timed out")
    except Exception as e:
        logger.error(f"  ✗ CCEI extraction error: {e}")


def run_weather_extraction():
    """
    Daily task: Extract weather data from Environment Canada.

    Runs 30 minutes after CCEI extraction (default: 06:30)
    """
    logger.info("Starting scheduled weather extraction...")

    try:
        script_path = get_project_root() / "scripts" / "weather_extract.py"

        if not script_path.exists():
            logger.error(f"weather_extract.py not found: {script_path}")
            return

        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5-minute timeout
        )

        if result.returncode == 0:
            logger.info("  ✓ Weather extraction completed successfully")
            logger.info(f"  Output: {result.stdout[:200]}")
        else:
            logger.error(f"  ✗ Weather extraction failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        logger.error("  ✗ Weather extraction timed out")
    except Exception as e:
        logger.error(f"  ✗ Weather extraction error: {e}")


def run_model_retrain():
    """
    Daily task: Retrain XGBoost model with latest data.

    Runs at time specified in settings.model_retrain_cron (default: 04:00)
    """
    logger.info("Starting scheduled model retraining...")

    try:
        r_script = get_project_root() / settings.r_script_path

        if not r_script.exists():
            logger.error(f"R model script not found: {r_script}")
            return

        # Train all horizons
        result = subprocess.run(
            [settings.rscript_bin, str(r_script)],
            capture_output=True,
            text=True,
            timeout=900  # 15-minute timeout
        )

        if result.returncode == 0:
            logger.info("  ✓ Model retraining completed successfully")
            logger.info(f"  Output: {result.stdout[:300]}")
        else:
            logger.error(f"  ✗ Model retraining failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        logger.error("  ✗ Model retraining timed out")
    except Exception as e:
        logger.error(f"  ✗ Model retraining error: {e}")


# ── Scheduler Management ──────────────────────────────────────────────────────

def start_scheduler():
    """
    Initialize and start the background scheduler.

    Schedules:
    - CCEI extraction: Daily at settings.ccei_poll_time (default: 06:00)
    - Weather extraction: Daily at 06:30 (30 min after CCEI)
    - Model retrain: Daily using settings.model_retrain_cron (default: 04:00)
    """

    # Parse CCEI poll time (HH:MM format)
    try:
        ccei_hour, ccei_minute = map(int, settings.ccei_poll_time.split(":"))
    except ValueError:
        logger.warning(f"Invalid CCEI_POLL_TIME format: {settings.ccei_poll_time}. Using default 06:00")
        ccei_hour, ccei_minute = 6, 0

    # Weather extraction runs 30 minutes after CCEI
    weather_hour = ccei_hour
    weather_minute = ccei_minute + 30
    if weather_minute >= 60:
        weather_hour += 1
        weather_minute -= 60

    # Add jobs
    scheduler.add_job(
        run_ccei_extraction,
        trigger="cron",
        hour=ccei_hour,
        minute=ccei_minute,
        id="ccei_extraction",
        name="Daily CCEI HFED Extraction",
        replace_existing=True
    )

    scheduler.add_job(
        run_weather_extraction,
        trigger="cron",
        hour=weather_hour,
        minute=weather_minute,
        id="weather_extraction",
        name="Daily Weather Extraction",
        replace_existing=True
    )

    # Model retrain using cron expression
    scheduler.add_job(
        run_model_retrain,
        trigger=CronTrigger.from_crontab(settings.model_retrain_cron),
        id="model_retrain",
        name="Daily Model Retraining",
        replace_existing=True
    )

    # Start the scheduler
    scheduler.start()

    logger.info("APScheduler jobs configured:")
    logger.info(f"  • CCEI extraction:    Daily at {ccei_hour:02d}:{ccei_minute:02d}")
    logger.info(f"  • Weather extraction: Daily at {weather_hour:02d}:{weather_minute:02d}")
    logger.info(f"  • Model retrain:      {settings.model_retrain_cron}")


def shutdown_scheduler():
    """Shutdown the scheduler gracefully"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


def get_scheduled_jobs():
    """
    Get information about scheduled jobs.

    Returns:
        List of job dictionaries with id, name, next run time
    """
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    return jobs
