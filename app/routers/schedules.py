from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.security import get_current_user, require_roles
from app.database import get_db
from app.models import (
    Appointment,
    Doctor,
    DoctorLeave,
    DoctorSchedule,
    Patient,
)
from app.schemas.schedule import (
    LeaveCreate,
    LeaveResponse,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
)
from app.utils.email import send_email

router = APIRouter(tags=["Doctor Schedules and Leaves"])

admin_only = require_roles("admin")

# Adjust these values to match your appointment status conventions.
FINAL_STATUSES = {"cancelled", "completed", "no_show"}


def get_doctor_or_404(db: Session, doctor_id: int):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()

    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")

    return doctor


def check_doctor_permission(doctor, current_user):
    """Allow admins any doctor; doctors only their own profile."""
    if current_user.role == "admin":
        return

    if current_user.role == "doctor" and doctor.user_id == current_user.id:
        return

    raise HTTPException(
        status_code=403,
        detail="You can manage only your own schedule and leave",
    )


def validate_schedule_values(
    start_time: time,
    end_time: time,
    break_start: time | None,
    break_end: time | None,
):
    if start_time >= end_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time",
        )

    # A break must have both endpoints or neither.
    if (break_start is None) != (break_end is None):
        raise HTTPException(
            status_code=400,
            detail="Provide both break_start and break_end, or leave both empty",
        )

    if break_start is not None and break_end is not None:
        if break_start >= break_end:
            raise HTTPException(
                status_code=400,
                detail="Break end time must be after break start time",
            )

        if break_start < start_time or break_end > end_time:
            raise HTTPException(
                status_code=400,
                detail="Break must be inside working hours",
            )


def schedules_overlap(
    start_a: time,
    end_a: time,
    start_b: time,
    end_b: time,
) -> bool:
    # Adjacent schedules are allowed: 09:00-12:00 and 12:00-15:00.
    return start_a < end_b and start_b < end_a


def check_schedule_overlap(
    db: Session,
    doctor_id: int,
    day_of_week: str,
    start_time: time,
    end_time: time,
    exclude_schedule_id: int | None = None,
):
    query = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doctor_id,
        DoctorSchedule.day_of_week == day_of_week,
        DoctorSchedule.is_active.is_(True),
    )

    if exclude_schedule_id is not None:
        query = query.filter(DoctorSchedule.id != exclude_schedule_id)

    for existing in query.all():
        if schedules_overlap(
            start_time,
            end_time,
            existing.start_time,
            existing.end_time,
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Schedule overlaps with an existing "
                    f"{day_of_week} schedule "
                    f"({existing.start_time}-{existing.end_time})"
                ),
            )


def get_slot_duration(doctor, schedule) -> int:
    duration = getattr(schedule, "slot_duration_minutes", None)
    if duration is None:
        duration = doctor.slot_duration_minutes

    if not duration or duration <= 0:
        raise HTTPException(
            status_code=400,
            detail="Doctor slot duration must be greater than zero",
        )

    return duration


def get_patient_email(appointment):
    patient = getattr(appointment, "patient", None)
    user = getattr(patient, "user", None) if patient else None

    if user and user.email:
        return user.email

    return None


@router.post(
    "/doctors/{doctor_id}/schedules",
    response_model=ScheduleResponse,
    status_code=201,
)
def create_schedule(
    doctor_id: int,
    request: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    doctor = get_doctor_or_404(db, doctor_id)
    check_doctor_permission(doctor, current_user)

    validate_schedule_values(
        request.start_time,
        request.end_time,
        request.break_start,
        request.break_end,
    )

    check_schedule_overlap(
        db,
        doctor_id,
        request.day_of_week,
        request.start_time,
        request.end_time,
    )

    duration = request.slot_duration_minutes or doctor.slot_duration_minutes

    if not duration or duration <= 0:
        raise HTTPException(
            status_code=400,
            detail="Slot duration must be greater than zero",
        )

    schedule = DoctorSchedule(
        doctor_id=doctor_id,
        day_of_week=request.day_of_week,
        start_time=request.start_time,
        end_time=request.end_time,
        break_start=request.break_start,
        break_end=request.break_end,
        slot_duration_minutes=duration,
        is_active=True,
    )

    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    return schedule


@router.get(
    "/doctors/{doctor_id}/schedules",
    response_model=list[ScheduleResponse],
)
def get_schedules(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    get_doctor_or_404(db, doctor_id)

    return (
        db.query(DoctorSchedule)
        .filter(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.is_active.is_(True),
        )
        .order_by(DoctorSchedule.day_of_week, DoctorSchedule.start_time)
        .all()
    )


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    request: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schedule = (
        db.query(DoctorSchedule)
        .filter(DoctorSchedule.id == schedule_id)
        .first()
    )

    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    doctor = get_doctor_or_404(db, schedule.doctor_id)
    check_doctor_permission(doctor, current_user)

    updates = request.model_dump(exclude_unset=True)

    start_time = updates.get("start_time", schedule.start_time)
    end_time = updates.get("end_time", schedule.end_time)
    break_start = updates.get("break_start", schedule.break_start)
    break_end = updates.get("break_end", schedule.break_end)
    day_of_week = updates.get("day_of_week", schedule.day_of_week)

    validate_schedule_values(start_time, end_time, break_start, break_end)

    if updates.get("is_active", schedule.is_active):
        check_schedule_overlap(
            db,
            schedule.doctor_id,
            day_of_week,
            start_time,
            end_time,
            exclude_schedule_id=schedule.id,
        )

    duration = updates.get(
        "slot_duration_minutes",
        schedule.slot_duration_minutes or doctor.slot_duration_minutes,
    )

    if not duration or duration <= 0:
        raise HTTPException(
            status_code=400,
            detail="Slot duration must be greater than zero",
        )

    for field, value in updates.items():
        setattr(schedule, field, value)

    db.commit()
    db.refresh(schedule)

    return schedule


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schedule = (
        db.query(DoctorSchedule)
        .filter(DoctorSchedule.id == schedule_id)
        .first()
    )

    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    doctor = get_doctor_or_404(db, schedule.doctor_id)
    check_doctor_permission(doctor, current_user)

    db.delete(schedule)
    db.commit()

    return {"message": "Schedule deleted successfully"}


@router.post(
    "/doctors/{doctor_id}/leaves",
    response_model=LeaveResponse,
    status_code=201,
)
def create_leave(
    doctor_id: int,
    request: LeaveCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    doctor = get_doctor_or_404(db, doctor_id)
    check_doctor_permission(doctor, current_user)

    # Prevent invalid date strings and return a clear validation error.
    try:
        leave_date = date.fromisoformat(request.leave_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="leave_date must use YYYY-MM-DD format",
        )

    existing_leave = db.query(DoctorLeave).filter(
        DoctorLeave.doctor_id == doctor_id,
        DoctorLeave.leave_date == leave_date,
    ).first()

    if existing_leave:
        raise HTTPException(
            status_code=409,
            detail="Leave already exists for this date",
        )

    leave = DoctorLeave(
        doctor_id=doctor_id,
        leave_date=leave_date,
        reason=request.reason,
    )

    try:
        db.add(leave)
        db.flush()

        # Cancel appointments that are not already in a final state.
        appointments = db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == leave_date,
        ).all()

        cancelled_count = 0

        for appointment in appointments:
            if (appointment.status or "").lower() in FINAL_STATUSES:
                continue

            email = get_patient_email(appointment)

            appointment.status = "Cancelled"
            cancelled_count += 1

            if email:
                patient_name = (
                    appointment.patient.user.full_name
                    if appointment.patient and appointment.patient.user
                    else "Patient"
                )

                subject = "Doctor leave - appointment cancelled"
                body = (
                    f"Hello {patient_name},\n\n"
                    f"Your appointment with Dr. {doctor.name} on "
                    f"{leave_date.isoformat()} at "
                    f"{appointment.appointment_time} has been cancelled "
                    "because the doctor is on leave.\n\n"
                    "Please log in to the hospital appointment system "
                    "to book another available slot.\n\n"
                    "We apologize for the inconvenience."
                )

                background_tasks.add_task(send_email, email, subject, body)

        db.commit()
        db.refresh(leave)

    except Exception:
        db.rollback()
        raise

    return leave


@router.get(
    "/doctors/{doctor_id}/leaves",
    response_model=list[LeaveResponse],
)
def get_leaves(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    doctor = get_doctor_or_404(db, doctor_id)

    # Leave records can expose reasons; restrict them to the admin
    # and the doctor who owns the profile.
    check_doctor_permission(doctor, current_user)

    return (
        db.query(DoctorLeave)
        .filter(DoctorLeave.doctor_id == doctor_id)
        .order_by(DoctorLeave.leave_date)
        .all()
    )


@router.get("/doctors/{doctor_id}/available-slots")
def get_available_slots(
    doctor_id: int,
    date: date = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    doctor = get_doctor_or_404(db, doctor_id)

    if not doctor.is_active:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if date < date.today():
        return {
            "doctor_id": doctor_id,
            "date": date.isoformat(),
            "available_slots": [],
        }

    leave = db.query(DoctorLeave).filter(
        DoctorLeave.doctor_id == doctor_id,
        DoctorLeave.leave_date == date,
    ).first()

    if leave:
        return {
            "doctor_id": doctor_id,
            "date": date.isoformat(),
            "available_slots": [],
            "message": "Doctor is on leave",
        }

    day_name = date.strftime("%A")

    schedules = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doctor_id,
        DoctorSchedule.day_of_week == day_name,
        DoctorSchedule.is_active.is_(True),
    ).order_by(DoctorSchedule.start_time).all()

    appointments = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == date,
    ).all()

    booked_times = {
        appointment.appointment_time
        for appointment in appointments
        if (appointment.status or "").lower() not in FINAL_STATUSES
    }

    now = datetime.now()
    available_slots = []

    for schedule in schedules:
        duration = get_slot_duration(doctor, schedule)
        current_time = datetime.combine(date, schedule.start_time)
        work_end = datetime.combine(date, schedule.end_time)

        break_start = (
            datetime.combine(date, schedule.break_start)
            if schedule.break_start is not None
            else None
        )
        break_end = (
            datetime.combine(date, schedule.break_end)
            if schedule.break_end is not None
            else None
        )

        while current_time + timedelta(minutes=duration) <= work_end:
            slot_end = current_time + timedelta(minutes=duration)

            overlaps_break = (
                break_start is not None
                and break_end is not None
                and current_time < break_end
                and break_start < slot_end
            )

            slot_time = current_time.time()

            is_past = date == now.date() and current_time <= now

            if (
                not overlaps_break
                and not is_past
                and slot_time not in booked_times
            ):
                available_slots.append(slot_time.strftime("%H:%M"))

            current_time = slot_end

    return {
        "doctor_id": doctor_id,
        "date": date.isoformat(),
        "available_slots": sorted(set(available_slots)),
    }