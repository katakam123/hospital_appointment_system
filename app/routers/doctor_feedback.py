from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import get_current_user
from app.models import Appointment
from app.models.doctor_feedback import DoctorFeedback

from app.schemas.doctor_feedback import (
    DoctorFeedbackCreate,
    DoctorFeedbackResponse,
)

router = APIRouter(
    tags=["Doctor Feedback"],
)


@router.post(
    "/appointments/{appointment_id}/feedback",
    response_model=DoctorFeedbackResponse,
    status_code=201,
)
def create_feedback(
    appointment_id: int,
    data: DoctorFeedbackCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found.",
        )

    # Adapt this ownership check to your Patient/User relationships.
    patient_id = getattr(appointment, "patient_id", None)

    if patient_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only review your own appointments.",
        )

    if appointment.status != "Completed":
        raise HTTPException(
            status_code=400,
            detail="Feedback is allowed only after a completed appointment.",
        )

    feedback = DoctorFeedback(
        appointment_id=appointment.id,
        doctor_id=appointment.doctor_id,
        patient_id=current_user.id,
        rating=data.rating,
        feedback=data.feedback.strip() if data.feedback else None,
    )

    try:
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Feedback has already been submitted for this appointment.",
        ) from exc


@router.get("/doctors/{doctor_id}/feedback")
def list_doctor_feedback(
    doctor_id: int,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if skip < 0 or limit < 1 or limit > 100:
        raise HTTPException(
            status_code=422,
            detail="skip must be non-negative and limit must be between 1 and 100.",
        )

    feedback = (
        db.query(DoctorFeedback)
        .filter(DoctorFeedback.doctor_id == doctor_id)
        .order_by(DoctorFeedback.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return feedback