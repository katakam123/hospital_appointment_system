
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DoctorCreate(BaseModel):
    user_id: int
    name: str = Field(min_length=2, max_length=150)
    department_id: int
    specialization: str = Field(min_length=2, max_length=150)
    qualification: str = Field(min_length=2, max_length=200)
    experience_years: int = Field(ge=0)
    consultation_fee: Decimal = Field(ge=0)
    slot_duration_minutes: int = Field(default=15, gt=0, le=240)


class DoctorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    department_id: int | None = None
    specialization: str | None = Field(default=None, min_length=2, max_length=150)
    qualification: str | None = Field(default=None, min_length=2, max_length=200)
    experience_years: int | None = Field(default=None, ge=0)
    consultation_fee: Decimal | None = Field(default=None, ge=0)
    slot_duration_minutes: int | None = Field(default=None, gt=0, le=240)
    is_active: bool | None = None


class DoctorResponse(BaseModel):
    id: int
    user_id: int
    name: str
    department_id: int
    specialization: str
    qualification: str
    experience_years: int
    consultation_fee: Decimal
    slot_duration_minutes: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
