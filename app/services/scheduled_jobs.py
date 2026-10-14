
import logging
from datetime import date, datetime, time, timedelta

from app.database import SessionLocal
from app.models import Appointment, Consultation
from app.services.email_service import (
    send_appointment_reminder_email,
    send_follow_up_reminder_email,
)

logger = logging.getLogger(__name__)


def get_patient_email(appointment):
    patient = appointment.patient
    user = getattr(patient, "user", None) if patient else None
    return getattr(user, "email", None)


def get_doctor_name(appointment):
    doctor = appointment.doctor
    user = getattr(doctor, "user", None) if doctor else None
    return (
        getattr(user, "full_name", None)
        or getattr(doctor, "name", None)
        or "Your doctor"
    )


def get_appointment_number(appointment):
    return str(
        getattr(appointment, "appointment_number", None)
        or appointment.id
    )


def appointment_datetime(appointment):
    """Combine the appointment date and time into one datetime."""
    appointment_date = appointment.appointment_date
    appointment_time = appointment.appointment_time

    if isinstance(appointment_time, timedelta):
        seconds = int(appointment_time.total_seconds())
        appointment_time = (
            datetime.min + timedelta(seconds=seconds)
        ).time()

    if isinstance(appointment_time, str):
        appointment_time = time.fromisoformat(appointment_time)

    return datetime.combine(appointment_date, appointment_time)


def send_upcoming_appointment_reminders():
    db = SessionLocal()
    now = datetime.now()
    end_time = now + timedelta(hours=24)

    try:
        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.reminder_sent.is_(False),
                Appointment.status == "Booked",
                Appointment.appointment_date >= now.date(),
                Appointment.appointment_date <= end_time.date(),
            )
            .all()
        )

        for appointment in appointments:
            try:
                slot = appointment_datetime(appointment)

                if not (now < slot <= end_time):
                    continue

                email = get_patient_email(appointment)
                if not email:
                    logger.warning(
                        "No patient email for appointment %s",
                        appointment.id,
                    )
                    continue

                success = send_appointment_reminder_email(
                    to_email=email,
                    appointment_number=get_appointment_number(appointment),
                    doctor_name=get_doctor_name(appointment),
                    appointment_date=str(appointment.appointment_date),
                    appointment_time=str(appointment.appointment_time),
                    token_number=appointment.token_number,
                )

                if success:
                    appointment.reminder_sent = True
                    db.commit()
                else:
                    db.rollback()

            except Exception:
                db.rollback()
                logger.exception(
                    "Reminder job failed for appointment %s",
                    appointment.id,
                )

    except Exception:
        logger.exception("Could not run appointment reminder job")
    finally:
        db.close()


def mark_no_show_appointments():
    db = SessionLocal()
    now = datetime.now()
    cutoff = now - timedelta(minutes=30)

    try:
        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.status == "Booked",
                Appointment.appointment_date <= cutoff.date(),
            )
            .all()
        )

        for appointment in appointments:
            try:
                slot = appointment_datetime(appointment)

                if slot > cutoff:
                    continue

                appointment.status = "No-Show"
                db.commit()

                logger.info(
                    "Appointment %s marked No-Show",
                    appointment.id,
                )

            except Exception:
                db.rollback()
                logger.exception(
                    "Could not mark appointment %s as No-Show",
                    appointment.id,
                )

    except Exception:
        logger.exception("Could not run no-show job")
    finally:
        db.close()


def send_follow_up_reminders():
    db = SessionLocal()
    tomorrow = date.today() + timedelta(days=1)

    try:
        consultations = (
            db.query(Consultation)
            .filter(Consultation.follow_up_date == tomorrow)
            .all()
        )

        for consultation in consultations:
            try:
                appointment = (
                    db.query(Appointment)
                    .filter(
                        Appointment.id == consultation.appointment_id
                    )
                    .first()
                )

                if not appointment:
                    continue

                email = get_patient_email(appointment)
                if not email:
                    continue

                send_follow_up_reminder_email(
                    to_email=email,
                    appointment_number=get_appointment_number(appointment),
                    follow_up_date=str(consultation.follow_up_date),
                )

            except Exception:
                logger.exception(
                    "Follow-up reminder failed for consultation %s",
                    consultation.id,
                )

    except Exception:
        logger.exception("Could not run follow-up reminder job")
    finally:
        db.close()
