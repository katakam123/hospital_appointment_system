from datetime import date, datetime, time, timedelta
from decimal import Decimal
from app.models import AppointmentHistory
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.database import get_db
from app.models import (
    Appointment,
    AppointmentSequence,
    Doctor,
    DoctorLeave,
    DoctorSchedule,
    Patient,
)
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
)

router = APIRouter(prefix="/appointments", tags=["Appointments"])

FINAL_STATUSES = {"cancelled", "completed", "no-show", "no_show"}


def get_patient_for_user(db: Session, user_id: int):
    patient = db.query(Patient).filter(
        Patient.user_id == user_id
    ).first()

    if patient is None:
        raise HTTPException(
            status_code=404,
            detail="Patient profile not found",
        )

    return patient


def allocate_appointment_number(db: Session, booking_date: date) -> str:
    """
    Allocate a daily sequence number using a locked MySQL row.
    The sequence update remains part of the appointment transaction.
    """
    statement = (
        mysql_insert(AppointmentSequence)
        .values(sequence_date=booking_date, last_number=0)
        .on_duplicate_key_update(
            last_number=AppointmentSequence.last_number
        )
    )

    db.execute(statement)

    sequence = (
        db.query(AppointmentSequence)
        .filter(AppointmentSequence.sequence_date == booking_date)
        .with_for_update()
        .one()
    )

    sequence.last_number += 1
    db.flush()

    return f"APT-{booking_date:%Y%m%d}-{sequence.last_number:04d}"


def validate_booking_slot(
    db: Session,
    doctor: Doctor,
    booking_date: date,
    slot_time: time,
):
    now = datetime.now()
    slot_start = datetime.combine(booking_date, slot_time)

    if slot_start <= now:
        raise HTTPException(
            status_code=400,
            detail="Appointments can only be booked for future slots",
        )

    if slot_start > now + timedelta(days=30):
        raise HTTPException(
            status_code=400,
            detail="Appointments can be booked at most 30 days in advance",
        )

    leave = db.query(DoctorLeave).filter(
        DoctorLeave.doctor_id == doctor.id,
        DoctorLeave.leave_date == booking_date,
    ).first()

    if leave:
        raise HTTPException(
            status_code=400,
            detail="Doctor is on leave on the selected date",
        )

    day_name = booking_date.strftime("%A")

    schedules = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doctor.id,
        DoctorSchedule.day_of_week == day_name,
        DoctorSchedule.is_active.is_(True),
    ).all()

    if not schedules:
        raise HTTPException(
            status_code=400,
            detail="Doctor has no active schedule on the selected day",
        )

    valid_slot = False

    for schedule in schedules:
        duration = (
            getattr(schedule, "slot_duration_minutes", None)
            or doctor.slot_duration_minutes
        )

        if not duration or duration <= 0:
            continue

        schedule_start = datetime.combine(
            booking_date, schedule.start_time
        )
        schedule_end = datetime.combine(
            booking_date, schedule.end_time
        )
        slot_end = slot_start + timedelta(minutes=duration)

        # A slot must fit entirely inside the working schedule.
        if slot_start < schedule_start or slot_end > schedule_end:
            continue

        # Slot start must align with the schedule's slot intervals.
        elapsed_seconds = (slot_start - schedule_start).total_seconds()
        slot_seconds = duration * 60

        if elapsed_seconds < 0 or elapsed_seconds % slot_seconds != 0:
            continue

        # Do not permit any overlap with the break.
        if schedule.break_start is not None and schedule.break_end is not None:
            break_start = datetime.combine(
                booking_date, schedule.break_start
            )
            break_end = datetime.combine(
                booking_date, schedule.break_end
            )

            if slot_start < break_end and break_start < slot_end:
                continue

        valid_slot = True
        break

    if not valid_slot:
        raise HTTPException(
            status_code=400,
            detail="Selected time is outside the doctor's available slots",
        )


def assign_daily_token_numbers(db: Session, doctor_id: int, booking_date: date):
    """
    Assign token numbers by slot time. If an earlier slot is booked later,
    subsequent tokens may be renumbered to preserve chronological order.
    """
    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == booking_date,
        )
        .order_by(
            Appointment.appointment_time,
            Appointment.id,
        )
        .all()
    )

    for token, appointment in enumerate(appointments, start=1):
        appointment.token_number = token

    db.flush()


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def book_appointment(
    request: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role != "patient":
        raise HTTPException(
            status_code=403,
            detail="Only patients can book appointments",
        )

    patient = get_patient_for_user(db, current_user.id)

    try:
        # Lock the patient row first to serialize this patient's bookings
        # across different doctors and prevent simultaneous double booking.
        locked_patient = (
            db.query(Patient)
            .filter(Patient.id == patient.id)
            .with_for_update()
            .first()
        )

        if locked_patient is None:
            raise HTTPException(
                status_code=404,
                detail="Patient profile not found",
            )

        # Lock the doctor row so concurrent bookings for the same doctor
        # are checked one at a time.
        doctor = (
            db.query(Doctor)
            .filter(Doctor.id == request.doctor_id)
            .with_for_update()
            .first()
        )

        if doctor is None or not doctor.is_active:
            raise HTTPException(
                status_code=404,
                detail="Active doctor not found",
            )

        validate_booking_slot(
            db,
            doctor,
            request.appointment_date,
            request.slot_time,
        )

        # One appointment for this patient at this date and time,
        # regardless of which doctor is selected.
        same_patient_time = db.query(Appointment).filter(
            Appointment.patient_id == locked_patient.id,
            Appointment.appointment_date == request.appointment_date,
            Appointment.appointment_time == request.slot_time,
        ).first()

        if same_patient_time:
            raise HTTPException(
                status_code=409,
                detail="You already have an appointment at this date and time",
            )

        # Only one appointment per patient per doctor per day.
        same_doctor_day = db.query(Appointment).filter(
            Appointment.patient_id == locked_patient.id,
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == request.appointment_date,
        ).first()

        if same_doctor_day:
            raise HTTPException(
                status_code=409,
                detail="You can book only one appointment with this doctor per day",
            )

        # Explicit slot check gives a useful error; the database constraint
        # below remains the final protection against concurrent duplicates.
        existing_slot = db.query(Appointment).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == request.appointment_date,
            Appointment.appointment_time == request.slot_time,
        ).first()

        if existing_slot:
            raise HTTPException(
                status_code=409,
                detail="This appointment slot has already been booked",
            )

        appointment_number = allocate_appointment_number(
            db, request.appointment_date
        )

        appointment = Appointment(
            appointment_number=appointment_number,
            patient_id=locked_patient.id,
            doctor_id=doctor.id,
            appointment_date=request.appointment_date,
            appointment_time=request.slot_time,
            token_number=1,
            reason=request.reason.strip() if request.reason else None,
            status="Booked",
            consultation_fee=Decimal(str(doctor.consultation_fee)),
        )

        db.add(appointment)
        db.flush()

        assign_daily_token_numbers(
            db, doctor.id, request.appointment_date
        )

        db.commit()
        db.refresh(appointment)

        return appointment

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "The appointment conflicts with an existing booking. "
                "Please select another slot."
            ),
        )
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=list[AppointmentResponse])
def get_appointments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Appointment)

    if current_user.role == "admin":
        return query.order_by(
            Appointment.appointment_date,
            Appointment.appointment_time,
        ).all()

    if current_user.role == "patient":
        patient = get_patient_for_user(db, current_user.id)
        query = query.filter(Appointment.patient_id == patient.id)

    elif current_user.role == "doctor":
        doctor = db.query(Doctor).filter(
            Doctor.user_id == current_user.id
        ).first()

        if doctor is None:
            raise HTTPException(
                status_code=404,
                detail="Doctor profile not found",
            )

        query = query.filter(Appointment.doctor_id == doctor.id)

    else:
        raise HTTPException(status_code=403, detail="Access forbidden")

    return query.order_by(
        Appointment.appointment_date,
        Appointment.appointment_time,
    ).all()


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id
    ).first()

    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    if current_user.role == "admin":
        return appointment

    if current_user.role == "patient":
        patient = get_patient_for_user(db, current_user.id)

        if appointment.patient_id != patient.id:
            raise HTTPException(status_code=403, detail="Access forbidden")

        return appointment

    if current_user.role == "doctor":
        doctor = db.query(Doctor).filter(
            Doctor.user_id == current_user.id
        ).first()

        if doctor is None or appointment.doctor_id != doctor.id:
            raise HTTPException(status_code=403, detail="Access forbidden")

        return appointment

    raise HTTPException(status_code=403, detail="Access forbidden")
def record_status_change(
    db,
    appointment,
    old_status: str,
    new_status: str,
    changed_by: int,
):
    history = AppointmentHistory(
        appointment_id=appointment.id,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        changed_at=datetime.utcnow(),
    )

    db.add(history)
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import get_current_user
from app.models import Appointment


@router.put("/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .with_for_update()
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    # Verify that this user owns the appointment.
    # Update this condition to match your Patient/User relationship.
    patient = appointment.patient

    if not patient or patient.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can cancel only your own appointment",
        )

    if appointment.status != "Booked":
        raise HTTPException(
            status_code=400,
            detail="Only Booked appointments can be cancelled",
        )

    slot_datetime = datetime.combine(
        appointment.appointment_date,
        appointment.appointment_time,
    )

    if datetime.now() > slot_datetime - timedelta(hours=2):
        raise HTTPException(
            status_code=400,
            detail="Cancellation must be at least 2 hours before the slot",
        )

    old_status = appointment.status
    appointment.status = "Cancelled"

    record_status_change(
        db=db,
        appointment=appointment,
        old_status=old_status,
        new_status="Cancelled",
        changed_by=current_user.id,
    )

    try:
        db.commit()
        db.refresh(appointment)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not cancel appointment",
        )

    return {
        "message": "Appointment cancelled successfully",
        "appointment_id": appointment.id,
        "status": appointment.status,
    }