
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DoctorFeedback(Base):
    __tablename__ = "doctor_feedback"

    __table_args__ = (
        UniqueConstraint(
            "appointment_id",
            name="uq_doctor_feedback_appointment",
        ),
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_doctor_feedback_rating",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"),
        nullable=False,
    )
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"),
        nullable=False,
        index=True,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
