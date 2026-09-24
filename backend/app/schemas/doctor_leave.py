from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DoctorLeaveBase(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
    reason: Optional[str] = None

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self


class DoctorLeaveCreate(DoctorLeaveBase):
    pass


class DoctorLeaveUpdate(BaseModel):
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    reason: Optional[str] = None

    @model_validator(mode="after")
    def end_after_start(self):
        if self.start_datetime is not None and self.end_datetime is not None and self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self


class DoctorLeaveInDBBase(DoctorLeaveBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class DoctorLeaveRead(DoctorLeaveInDBBase):
    """Named distinctly from the ORM model app.models.doctor_leave.DoctorLeave."""

    pass


class DoctorLeaveWriteResponse(DoctorLeaveInDBBase):
    """
    Response for create/update: same fields as DoctorLeaveRead, plus the ids
    of any already-scheduled appointments that fall inside this leave
    period. The leave is still created/updated either way — a doctor going
    on leave doesn't retroactively cancel existing bookings — but the caller
    (the doctor-schedule UI) needs to know so a human can follow up (reassign
    or cancel those appointments) instead of them silently going unseen.
    """

    conflicting_appointment_ids: list[int] = []
