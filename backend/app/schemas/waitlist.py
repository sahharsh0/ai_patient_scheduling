import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import WaitlistStatus


class WaitlistBase(BaseModel):
    specialization_id: int
    preferred_date: dt.date
    earliest_time: Optional[dt.time] = None
    latest_time: Optional[dt.time] = None
    priority: int = Field(0, ge=0, le=10)

    @model_validator(mode="after")
    def times_ordered(self):
        if self.earliest_time and self.latest_time and self.latest_time <= self.earliest_time:
            raise ValueError("latest_time must be after earliest_time")
        return self


class WaitlistCreate(WaitlistBase):
    pass


class WaitlistRead(WaitlistBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    status: WaitlistStatus
    created_at: dt.datetime
