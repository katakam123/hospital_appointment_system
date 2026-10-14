import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str) -> None:
    host = getattr(settings, "SMTP_HOST", None)
    port = getattr(settings, "SMTP_PORT", 587)
    username = getattr(settings, "SMTP_USERNAME", None)
    password = getattr(settings, "SMTP_PASSWORD", None)
    from_email = getattr(settings, "SMTP_FROM_EMAIL", None)
    use_tls = getattr(settings, "SMTP_USE_TLS", True)

    if not host or not from_email:
        logger.warning("Email not sent: SMTP_HOST or SMTP_FROM_EMAIL is missing")
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()

            if username and password:
                server.login(username, password)

            server.send_message(message)

    except Exception:
        logger.exception("Failed to send email to %s", to_email)