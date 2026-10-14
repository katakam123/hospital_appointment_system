from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date, datetime, time
from datetime import date
from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    Numeric,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Import Appointment only after confirming its actual class name.

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="patient", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    doctor: Mapped["Doctor | None"] = relationship(
        back_populates="user", uselist=False
    )
    patient: Mapped["Patient | None"] = relationship(
        back_populates="user", uselist=False
    )


class Department(TimestampMixin, Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    doctors: Mapped[list["Doctor"]] = relationship(back_populates="department")


class Doctor(TimestampMixin, Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"), nullable=False
    )
    specialization: Mapped[str] = mapped_column(String(150), nullable=False)
    qualification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consultation_fee: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="doctor")
    department: Mapped["Department"] = relationship(back_populates="doctors")
    schedules: Mapped[list["DoctorSchedule"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    leaves: Mapped[list["DoctorLeave"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="doctor"
    )


class Patient(TimestampMixin, Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="patient")
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="patient"
    )


class DoctorSchedule(TimestampMixin, Base):
    __tablename__ = "doctor_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    break_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    slot_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    doctor: Mapped["Doctor"] = relationship(back_populates="schedules")


class DoctorLeave(TimestampMixin, Base):
    __tablename__ = "doctor_leaves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id"), nullable=False
    )
    leave_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    doctor: Mapped["Doctor"] = relationship(back_populates="leaves")


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint(
            "doctor_id",
            "appointment_date",
            "appointment_time",
            name="uq_doctor_appointment_slot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    appointment_number: Mapped[str] = mapped_column(
        String(40), unique=True, index=True, nullable=False
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), nullable=False
    )
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id"), nullable=False
    )
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    appointment_time: Mapped[time] = mapped_column(Time, nullable=False)
    token_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="Booked", nullable=False
    )
    consultation_fee: Mapped[int] = mapped_column(Integer, nullable=False)
    reschedule_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    checked_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    patient: Mapped["Patient"] = relationship(back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship(back_populates="appointments")
    consultation: Mapped["Consultation | None"] = relationship(
        back_populates="appointment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Consultation(TimestampMixin, Base):
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"), unique=True, nullable=False
    )
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    prescription: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    appointment: Mapped["Appointment"] = relationship(
        back_populates="consultation"
    )
    files: Mapped[list["ConsultationFile"]] = relationship(
        back_populates="consultation",
        cascade="all, delete-orphan",
    )


class ConsultationFile(TimestampMixin, Base):
    __tablename__ = "consultation_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    consultation_id: Mapped[int] = mapped_column(
        ForeignKey("consultations.id"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    consultation: Mapped["Consultation"] = relationship(back_populates="files")


from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Store a SHA-256 hash rather than the raw refresh token.
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    user: Mapped["User"] = relationship()
class AppointmentSequence(Base):
    __tablename__ = "appointment_sequences"

    sequence_date: Mapped[date] = mapped_column(
        Date,
        primary_key=True
    )

    last_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
class AppointmentHistory(Base):
    __tablename__ = "appointment_history"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"),
        nullable=False,
        index=True
    )

    old_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    new_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    changed_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
