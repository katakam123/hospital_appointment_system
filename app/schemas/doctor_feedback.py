
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DoctorFeedbackCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    feedback: str | None = Field(default=None, max_length=2000)

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                return None
        return value


class DoctorFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_id: int
    doctor_id: int
    patient_id: int
    rating: int
    feedback: str | None
    created_at: datetime
