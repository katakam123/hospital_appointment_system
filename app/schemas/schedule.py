from datetime import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DayOfWeek = Literal[
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


class ScheduleCreate(BaseModel):
    day_of_week: DayOfWeek
    start_time: time
    end_time: time
    break_start: time | None = None
    break_end: time | None = None
    slot_duration_minutes: int | None = Field(default=None, gt=0, le=240)


class ScheduleUpdate(BaseModel):
    day_of_week: DayOfWeek | None = None
    start_time: time | None = None
    end_time: time | None = None
    break_start: time | None = None
    break_end: time | None = None
    slot_duration_minutes: int | None = Field(default=None, gt=0, le=240)
    is_active: bool | None = None


class ScheduleResponse(BaseModel):
    id: int
    doctor_id: int
    day_of_week: str
    start_time: time
    end_time: time
    break_start: time | None
    break_end: time | None
    slot_duration_minutes: int | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class LeaveCreate(BaseModel):
    leave_date: str
    reason: str | None = None


class LeaveResponse(BaseModel):
    id: int
    doctor_id: int
    leave_date: str
    reason: str | None

    model_config = ConfigDict(from_attributes=True)