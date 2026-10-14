from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import get_current_user
from app.models import Appointment, AppointmentHistory, Consultation
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationResponse,
)

router = APIRouter(tags=["Consultations"])


@router.post(
    "/appointments/{appointment_id}/consultation",
    response_model=ConsultationResponse,
)
def create_consultation(
    appointment_id: int,
    data: ConsultationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role != "doctor":
        raise HTTPException(
            status_code=403,
            detail="Only doctors can create consultations",
        )

    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .with_for_update()
        .first()
    )

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    if (
        not appointment.doctor
        or appointment.doctor.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not the doctor assigned to this appointment",
        )

    if appointment.status != "In Consultation":
        raise HTTPException(
            status_code=400,
            detail="Appointment must be In Consultation",
        )

    existing = (
        db.query(Consultation)
        .filter(Consultation.appointment_id == appointment_id)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Consultation already exists for this appointment",
        )

    consultation = Consultation(
        appointment_id=appointment_id,
        symptoms=data.symptoms,
        diagnosis=data.diagnosis,
        prescription=data.prescription,
        advice=data.advice,
        follow_up_date=data.follow_up_date,
    )

    old_status = appointment.status
    appointment.status = "Completed"

    db.add(consultation)
    db.add(
        AppointmentHistory(
            appointment_id=appointment.id,
            old_status=old_status,
            new_status="Completed",
            changed_by=current_user.id,
            changed_at=datetime.utcnow(),
        )
    )

    try:
        db.commit()
        db.refresh(consultation)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save consultation",
        )

    return consultation


@router.get(
    "/appointments/{appointment_id}/consultation",
    response_model=ConsultationResponse,
)
def get_consultation(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    allowed = current_user.role == "admin"

    if (
        current_user.role == "patient"
        and appointment.patient
        and appointment.patient.user_id == current_user.id
    ):
        allowed = True

    if (
        current_user.role == "doctor"
        and appointment.doctor
        and appointment.doctor.user_id == current_user.id
    ):
        allowed = True

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="You cannot view this consultation",
        )

    consultation = (
        db.query(Consultation)
        .filter(Consultation.appointment_id == appointment_id)
        .first()
    )

    if not consultation:
        raise HTTPException(404, "Consultation not found")

    return consultation