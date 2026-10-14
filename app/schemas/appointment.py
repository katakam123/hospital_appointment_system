from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AppointmentCreate(BaseModel):
    doctor_id: int = Field(gt=0)
    appointment_date: date
    slot_time: time
    reason: str | None = Field(default=None, max_length=1000)


class AppointmentResponse(BaseModel):
    id: int
    appointment_number: str
    patient_id: int
    doctor_id: int
    appointment_date: date
    slot_time: time = Field(
        validation_alias="appointment_time",
        serialization_alias="slot_time",
    )
    token_number: int
    reason: str | None
    status: str
    consultation_fee: Decimal

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
class AppointmentReschedule(BaseModel):
    appointment_date: date
    appointment_time: time

    model_config = ConfigDict(extra="forbid")