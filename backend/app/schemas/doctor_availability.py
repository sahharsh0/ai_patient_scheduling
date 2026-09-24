from datetime import time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DoctorAvailabilityBase(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    start_time: time
    end_time: time
    slot_duration: int = Field(30, ge=5, le=120, description="Slot duration in minutes")

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class DoctorAvailabilityCreate(DoctorAvailabilityBase):
    pass


class DoctorAvailabilityUpdate(BaseModel):
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    slot_duration: Optional[int] = Field(None, ge=5, le=120)

    @model_validator(mode="after")
    def end_after_start(self):
        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class DoctorAvailabilityInDBBase(DoctorAvailabilityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class DoctorAvailabilityRead(DoctorAvailabilityInDBBase):
    """Named distinctly from the ORM model app.models.doctor_availability.DoctorAvailability."""

    pass
