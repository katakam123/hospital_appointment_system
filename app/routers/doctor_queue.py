
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import get_current_user
from app.models import Doctor, Appointment, AppointmentHistory
from app.services.live_queue_service import broadcast_queue_update

router = APIRouter(prefix="/doctors", tags=["Doctor Queue"])


@router.put("/me/call-next")
async def call_next_patient(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if str(current_user.role).lower() != "doctor":
        raise HTTPException(status_code=403, detail="Doctors only")

    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id)
        .first()
    )

    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    today = date.today()

    try:
        current = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor.id,
                Appointment.appointment_date == today,
                Appointment.status == "In Consultation",
            )
            .first()
        )

        if current:
            raise HTTPException(
                status_code=409,
                detail="Save the current consultation before calling the next patient",
            )

        next_appointment = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor.id,
                Appointment.appointment_date == today,
                Appointment.status == "Checked-In",
            )
            .order_by(Appointment.token_number.asc())
            .with_for_update()
            .first()
        )

        if not next_appointment:
            raise HTTPException(
                status_code=404,
                detail="No checked-in patients are waiting",
            )

        old_status = next_appointment.status
        next_appointment.status = "In Consultation"

        history = AppointmentHistory(
            appointment_id=next_appointment.id,
            old_status=old_status,
            new_status="In Consultation",
            changed_by=current_user.id,
            changed_at=datetime.utcnow(),
        )
        db.add(history)
        db.commit()
        db.refresh(next_appointment)

        await broadcast_queue_update(db, doctor.id)

        # Tell the patient that their turn has started.
        patient_user_id = (
            next_appointment.patient.user_id
            if next_appointment.patient
            else None
        )
        if patient_user_id:
            from app.services.websocket_manager import manager
            await manager.notify_user(
                patient_user_id,
                {
                    "event": "your_turn",
                    "message": "You are next, please be ready",
                    "appointment_id": next_appointment.id,
                    "token_number": next_appointment.token_number,
                },
            )

        return {
            "message": "Next patient called",
            "appointment_id": next_appointment.id,
            "token_number": next_appointment.token_number,
            "status": next_appointment.status,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
