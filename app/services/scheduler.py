import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.services.scheduled_jobs import (
    mark_no_show_appointments,
    send_follow_up_reminders,
    send_upcoming_appointment_reminders,
)

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")


def start_scheduler():
    if scheduler.running:
        logger.info("APScheduler is already running")
        return

    scheduler.add_job(
        send_upcoming_appointment_reminders,
        trigger="interval",
        hours=1,
        id="appointment_reminders",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        mark_no_show_appointments,
        trigger="interval",
        minutes=15,
        id="appointment_no_show",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        send_follow_up_reminders,
        trigger="cron",
        hour=8,
        minute=0,
        id="follow_up_reminders",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    logger.info("APScheduler started successfully")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")