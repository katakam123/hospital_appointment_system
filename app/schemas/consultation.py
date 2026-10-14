from datetime import date
from pydantic import BaseModel, ConfigDict


class ConsultationCreate(BaseModel):
    symptoms: str
    diagnosis: str
    prescription: str | None = None
    advice: str | None = None
    follow_up_date: date | None = None


class ConsultationResponse(ConsultationCreate):
    id: int
    appointment_id: int

    model_config = ConfigDict(from_attributes=True)