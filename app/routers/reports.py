from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.department import Department
from app.auth.security import require_roles
from app.models import Appointment, Doctor, Department, User
router = APIRouter(
    prefix="/reports",
    tags=["Admin Reports"],
    dependencies=[Depends(require_roles("Admin"))],
)

HOSPITAL_TZ = ZoneInfo("Asia/Kolkata")


def hospital_today() -> date:
    return datetime.now(HOSPITAL_TZ).date()


def validate_date_range(start_date: date, end_date: date):
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be after end_date.",
        )


def appointment_date_filter(query, start_date, end_date):
    # This version assumes appointment_date is a SQL DATE column.
    return query.filter(
        Appointment.appointment_date >= start_date,
        Appointment.appointment_date <= end_date,
    )


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    today = hospital_today()

    rows = (
        db.query(
            Appointment.status,
            func.count(Appointment.id),
        )
        .filter(Appointment.appointment_date == today)
        .group_by(Appointment.status)
        .all()
    )

    counts = {status: count for status, count in rows}

    # Assumption: consultation revenue is stored as
    # Appointment.consultation_fee. Replace this expression if your
    # project stores the actual charged fee on Consultation instead.
    revenue = (
        db.query(func.coalesce(func.sum(Appointment.consultation_fee), 0))
        .filter(
            Appointment.appointment_date == today,
            Appointment.status == "Completed",
        )
        .scalar()
    )

    return {
        "date": today,
        "total_appointments": sum(counts.values()),
        "checked_in": counts.get("Checked-In", 0),
        "completed": counts.get("Completed", 0),
        "cancelled": counts.get("Cancelled", 0),
        "no_shows": counts.get("No-Show", 0),
        "consultation_revenue": float(revenue or 0),
    }


@router.get("/doctor-performance")
def doctor_performance(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
):
    validate_date_range(start_date, end_date)

    # This example assumes Doctor.department_id and Appointment.doctor_id.
    query = (
        db.query(
            Doctor.id.label("doctor_id"),
            Doctor.name.label("doctor_name"),
            func.count(Appointment.id).label("appointments"),
            func.sum(
                case(
                    (Appointment.status == "Completed", 1),
                    else_=0,
                )
            ).label("completed"),
            func.sum(
                case(
                    (Appointment.status == "No-Show", 1),
                    else_=0,
                )
            ).label("no_shows"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            Appointment.status == "Completed",
                            Appointment.consultation_fee,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("revenue"),
        )
        .outerjoin(
            Appointment,
            (Appointment.doctor_id == Doctor.id)
            & (Appointment.appointment_date >= start_date)
            & (Appointment.appointment_date <= end_date),
        )
        .group_by(Doctor.id, Doctor.name)
        .order_by(Doctor.name)
        .all()
    )

    results = []

    for row in query:
        total = row.appointments or 0
        no_shows = row.no_shows or 0

        results.append({
            "doctor_id": row.doctor_id,
            "doctor_name": row.doctor_name,
            "appointments": total,
            "completed_consultations": row.completed or 0,
            "no_show_percentage": round(
                no_shows * 100 / total, 2
            ) if total else 0,
            "revenue": float(row.revenue or 0),
        })

    return {
        "start_date": start_date,
        "end_date": end_date,
        "doctors": results,
    }


@router.get("/department-summary")
def department_summary(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
):
    validate_date_range(start_date, end_date)

    rows = (
        db.query(
            Department.id.label("department_id"),
            Department.department_name.label("department_name"),
            func.count(Appointment.id).label("appointment_count"),
        )
        .join(Doctor, Doctor.department_id == Department.id)
        .join(Appointment, Appointment.doctor_id == Doctor.id)
        .filter(
            Appointment.appointment_date >= start_date,
            Appointment.appointment_date <= end_date,
        )
        .group_by(Department.id, Department.department_name)
        .order_by(Department.department_name)
        .all()
    )

    return [
        {
            "department_id": row.department_id,
            "department_name": row.department_name,
            "appointment_count": row.appointment_count,
        }
        for row in rows
    ]


@router.get("/peak-hours")
def peak_hours(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
):
    validate_date_range(start_date, end_date)

    # Assumes appointment_time is a SQL TIME column.
    hour_expression = func.hour(Appointment.appointment_time)

    rows = (
        db.query(
            hour_expression.label("hour"),
            func.count(Appointment.id).label("appointment_count"),
        )
        .filter(
            Appointment.appointment_date >= start_date,
            Appointment.appointment_date <= end_date,
        )
        .group_by(hour_expression)
        .all()
    )

    counts = {int(row.hour): row.appointment_count for row in rows}

    return {
        "start_date": start_date,
        "end_date": end_date,
        "hours": [
            {
                "hour": hour,
                "label": f"{hour:02d}:00",
                "appointment_count": counts.get(hour, 0),
            }
            for hour in range(24)
        ],
    }


@router.get("/frequent-no-shows")
def frequent_no_shows(db: Session = Depends(get_db)):
    from app.models.user import User

    today = hospital_today()
    start_date = today - timedelta(days=89)

    # Assumes Appointment.patient_id references User.id.
    # If patient_id references a Patient table instead, join through
    # Patient to User using your actual model relationships.
    rows = (
        db.query(
            User.id.label("patient_id"),
            User.full_name.label("patient_name"),
            func.count(Appointment.id).label("no_show_count"),
        )
        .join(Appointment, Appointment.patient_id == User.id)
        .filter(
            Appointment.status == "No-Show",
            Appointment.appointment_date >= start_date,
            Appointment.appointment_date <= today,
        )
        .group_by(User.id, User.full_name)
        .having(func.count(Appointment.id) >= 3)
        .order_by(func.count(Appointment.id).desc())
        .all()
    )

    return [
        {
            "patient_id": row.patient_id,
            "patient_name": row.patient_name,
            "no_show_count": row.no_show_count,
        }
        for row in rows
    ]