
from datetime import date

from app.models import Appointment, DoctorSchedule
from app.services.websocket_manager import manager
from app.database import SessionLocal

def get_slot_duration(db, doctor_id: int) -> int:
    """
    Assumes DoctorSchedule has doctor_id and slot_duration_minutes.
    Change these field names if your model uses different names.
    """
    schedule = (
        db.query(DoctorSchedule)
        .filter(DoctorSchedule.doctor_id == doctor_id)
        .first()
    )

    if not schedule:
        return 15

    return int(getattr(schedule, "slot_duration_minutes", 15))


def build_queue_snapshot(db, doctor_id: int) -> dict:
    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == date.today(),
            Appointment.status.in_(
                ["Checked-In", "In Consultation"]
            ),
        )
        .order_by(Appointment.token_number.asc())
        .all()
    )

    current = next(
        (
            appointment
            for appointment in appointments
            if appointment.status == "In Consultation"
        ),
        None,
    )

    waiting = [
        appointment
        for appointment in appointments
        if appointment.status == "Checked-In"
    ]

    slot_minutes = get_slot_duration(db, doctor_id)

    waiting_patients = []

    for position, appointment in enumerate(waiting, start=1):
        waiting_patients.append({
            "appointment_id": appointment.id,
            "token_number": appointment.token_number,
            "position": position,
            "estimated_wait_minutes": position * slot_minutes,
        })

    return {
        "event": "queue_update",
        "doctor_id": doctor_id,
        "date": date.today().isoformat(),
        "current_token": (
            current.token_number if current else None
        ),
        "waiting_count": len(waiting),
        "slot_duration_minutes": slot_minutes,
        "waiting_patients": waiting_patients,
    }


async def broadcast_queue_update(db, doctor_id: int):
    snapshot = build_queue_snapshot(db, doctor_id)
    await manager.broadcast_queue(doctor_id, snapshot)
async def refresh_and_broadcast_queue(doctor_id: int):
    db = SessionLocal()
    try:
        await broadcast_queue_update(db, doctor_id)
    finally:
        db.close()