
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.security import get_current_user, require_roles
from app.database import get_db
from app.models import Appointment, Department, Doctor, User
from app.schemas.doctor import DoctorCreate, DoctorUpdate, DoctorResponse

router = APIRouter(prefix="/doctors", tags=["Doctors"])

admin_only = require_roles("admin")

# Appointments in these states do not count as upcoming active appointments.
FINAL_STATUSES = ("cancelled", "completed", "no_show")


def get_doctor_or_404(db: Session, doctor_id: int):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()

    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")

    return doctor


def has_upcoming_appointments(db: Session, doctor_id: int) -> bool:
    now = datetime.now()

    return (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            or_(
                Appointment.appointment_date > now.date(),
                (
                    (Appointment.appointment_date == now.date())
                    & (Appointment.appointment_time >= now.time())
                ),
            ),
            Appointment.status.notin_(FINAL_STATUSES),
        )
        .first()
        is not None
    )


def validate_department(db: Session, department_id: int):
    department = db.query(Department).filter(
        Department.id == department_id
    ).first()

    if department is None or not department.is_active:
        raise HTTPException(
            status_code=400,
            detail="Department not found or inactive",
        )


@router.post(
    "",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_doctor(
    request: DoctorCreate,
    db: Session = Depends(get_db),
    current_user=Depends(admin_only),
):
    user = db.query(User).filter(
        User.id == request.user_id
    ).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role != "doctor":
        raise HTTPException(
            status_code=400,
            detail="The linked user must have the doctor role",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Cannot create a doctor profile for an inactive user",
        )

    existing_profile = db.query(Doctor).filter(
        Doctor.user_id == request.user_id
    ).first()

    if existing_profile:
        raise HTTPException(
            status_code=409,
            detail="This user already has a doctor profile",
        )

    validate_department(db, request.department_id)

    doctor = Doctor(
        user_id=request.user_id,
        name=request.name.strip(),
        department_id=request.department_id,
        specialization=request.specialization.strip(),
        qualification=request.qualification.strip(),
        experience_years=request.experience_years,
        consultation_fee=request.consultation_fee,
        slot_duration_minutes=request.slot_duration_minutes,
        is_active=True,
    )

    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    return doctor


@router.get("", response_model=list[DoctorResponse])
def get_doctors(
    department_id: int | None = Query(default=None, gt=0),
    specialization: str | None = Query(default=None, min_length=1),
    name: str | None = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Doctor)

    # Patients must never see inactive doctors.
    if current_user.role == "patient":
        query = query.filter(Doctor.is_active.is_(True))

    if department_id is not None:
        query = query.filter(Doctor.department_id == department_id)

    if specialization and specialization.strip():
        query = query.filter(
            Doctor.specialization.ilike(f"%{specialization.strip()}%")
        )

    if name and name.strip():
        query = query.filter(Doctor.name.ilike(f"%{name.strip()}%"))

    return query.order_by(Doctor.name).all()


@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    doctor = get_doctor_or_404(db, doctor_id)

    if current_user.role == "patient" and not doctor.is_active:
        raise HTTPException(status_code=404, detail="Doctor not found")

    return doctor


@router.put("/{doctor_id}", response_model=DoctorResponse)
def update_doctor(
    doctor_id: int,
    request: DoctorUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(admin_only),
):
    doctor = get_doctor_or_404(db, doctor_id)
    updates = request.model_dump(exclude_unset=True)

    if updates.get("department_id") is not None:
        validate_department(db, updates["department_id"])

    if updates.get("is_active") is False and doctor.is_active:
        if has_upcoming_appointments(db, doctor.id):
            raise HTTPException(
                status_code=409,
                detail="Cannot deactivate a doctor with upcoming appointments",
            )

    for field, value in updates.items():
        if isinstance(value, str) and field in {
            "name", "specialization", "qualification"
        }:
            value = value.strip()
            if not value:
                raise HTTPException(
                    status_code=400,
                    detail=f"{field} cannot be empty",
                )

        setattr(doctor, field, value)

    db.commit()
    db.refresh(doctor)

    return doctor


@router.delete("/{doctor_id}")
def delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(admin_only),
):
    doctor = get_doctor_or_404(db, doctor_id)

    if not doctor.is_active:
        return {"message": "Doctor is already inactive"}

    if has_upcoming_appointments(db, doctor.id):
        raise HTTPException(
            status_code=409,
            detail="Cannot deactivate a doctor with upcoming appointments",
        )

    # Soft delete: preserve the doctor record and appointment history.
    doctor.is_active = False
    db.commit()

    return {"message": "Doctor deactivated successfully"}
