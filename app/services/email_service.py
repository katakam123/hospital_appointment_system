
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send one email. Return False and log the error on failure."""
    if not to_email:
        logger.warning("Email skipped: recipient address is empty")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = (
        settings.smtp_from_email or settings.smtp_username
    )
    message["To"] = to_email
    message.set_content(body)

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=15,
        ) as server:
            if settings.smtp_use_tls:
                server.starttls()

            if settings.smtp_username:
                server.login(
                    settings.smtp_username,
                    settings.smtp_password,
                )

            server.send_message(message)

        logger.info("Email sent to %s: %s", to_email, subject)
        return True

    except Exception:
        logger.exception(
            "Failed to send email to %s: %s",
            to_email,
            subject,
        )
        return False


def send_appointment_booked_email(
    to_email: str,
    appointment_number: str,
    doctor_name: str,
    appointment_date: str,
    appointment_time: str,
    token_number: int,
):
    body = (
        "Your hospital appointment has been booked.\n\n"
        f"Appointment number: {appointment_number}\n"
        f"Doctor: {doctor_name}\n"
        f"Date: {appointment_date}\n"
        f"Time: {appointment_time}\n"
        f"Token number: {token_number}\n\n"
        "Please arrive on time."
    )
    return send_email(to_email, "Appointment Booked", body)


def send_appointment_status_email(
    to_email: str,
    appointment_number: str,
    status: str,
    appointment_date: str,
    appointment_time: str,
):
    body = (
        f"Your appointment {appointment_number} has been {status}.\n\n"
        f"Date: {appointment_date}\n"
        f"Time: {appointment_time}\n"
    )
    return send_email(to_email, f"Appointment {status}", body)


def send_consultation_completed_email(
    to_email: str,
    appointment_number: str,
    follow_up_date: str | None = None,
):
    body = (
        f"Your consultation for appointment {appointment_number} "
        "has been completed.\n"
    )

    if follow_up_date:
        body += f"Your follow-up date is {follow_up_date}.\n"
    else:
        body += "No follow-up date has been scheduled.\n"

    return send_email(to_email, "Consultation Completed", body)


def send_appointment_reminder_email(
    to_email: str,
    appointment_number: str,
    doctor_name: str,
    appointment_date: str,
    appointment_time: str,
    token_number: int,
):
    body = (
        "This is a reminder for your upcoming appointment.\n\n"
        f"Appointment number: {appointment_number}\n"
        f"Doctor: {doctor_name}\n"
        f"Date: {appointment_date}\n"
        f"Time: {appointment_time}\n"
        f"Token number: {token_number}\n"
    )
    return send_email(to_email, "Appointment Reminder", body)


def send_follow_up_reminder_email(
    to_email: str,
    appointment_number: str,
    follow_up_date: str,
):
    body = (
        f"This is a reminder that your follow-up date is "
        f"{follow_up_date}.\n"
        f"Appointment number: {appointment_number}\n"
    )
    return send_email(to_email, "Follow-up Reminder", body)
