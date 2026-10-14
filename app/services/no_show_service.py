from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Appointment


def mark_no_show_appointments(db: Session):
    now = datetime.now()

    appointments = (
        db.query(Appointment)
        .filter(Appointment.status == "Booked")
        .with_for_update()
        .all()
    )

    changed_count = 0

    try:
        for appointment in appointments:
            slot_datetime = datetime.combine(
                appointment.appointment_date,
                appointment.appointment_time,
            )

            if now >= slot_datetime + timedelta(minutes=30):
                old_status = appointment.status
                appointment.status = "No-Show"

                # Use the actual ID of a dedicated system user
                # if changed_by has a non-null foreign key.
                record_status_change(
                    db=db,
                    appointment=appointment,
                    old_status=old_status,
                    new_status="No-Show",
                    changed_by=SYSTEM_USER_ID,
                )

                changed_count += 1

        db.commit()
        return changed_count

    except Exception:
        db.rollback()
        raise