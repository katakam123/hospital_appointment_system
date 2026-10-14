
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import get_current_user
from app.models import Appointment, Consultation

router = APIRouter(tags=["Patient History"])


@router.get("/patients/me/history")
def get_patient_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Only patients can view their own history.
    if current_user.role != "Patient":
        raise HTTPException(
            status_code=403,
            detail="Only patients can view their history",
        )

    appointments = (
        db.query(Appointment)
        .filter(Appointment.patient.has(user_id=current_user.id))
        .order_by(Appointment.appointment_date.desc())
        .all()
    )

    history = []

    for appointment in appointments:
        consultation = (
            db.query(Consultation)
            .filter(
                Consultation.appointment_id == appointment.id
            )
            .first()
        )

        history.append({
            "appointment_id": appointment.id,
            "appointment_number": getattr(
                appointment, "appointment_number", None
            ),
            "doctor_id": appointment.doctor_id,
            "appointment_date": str(appointment.appointment_date),
            "appointment_time": str(appointment.appointment_time),
            "status": appointment.status,
            "diagnosis": (
                consultation.diagnosis if consultation else None
            ),
            "symptoms": (
                consultation.symptoms if consultation else None
            ),
            "prescription": (
                consultation.prescription if consultation else None
            ),
            "advice": (
                consultation.advice if consultation else None
            ),
            "follow_up_date": (
                str(consultation.follow_up_date)
                if consultation and consultation.follow_up_date
                else None
            ),
        })

    return history
