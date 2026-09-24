from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.enums import AppointmentStatus, AppointmentType, BookingSource


class AppointmentBase(BaseModel):
    patient_id: int
    doctor_id: int
    specialization_id: int
    start_datetime: datetime
    end_datetime: datetime
    appointment_type: AppointmentType = AppointmentType.consultation
    booking_source: BookingSource = BookingSource.normal

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self


class AppointmentCreate(AppointmentBase):
    # patient_id is optional here and, when a patient books, is ALWAYS
    # overwritten server-side from the authenticated user (see
    # app/api/appointments.py:book_appointment) — the client is never
    # trusted to supply it. It's still part of AppointmentBase because
    # internal callers (e.g. admin tooling) may need to set it explicitly.
    patient_id: Optional[int] = None


class AppointmentUpdate(BaseModel):
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    appointment_type: Optional[AppointmentType] = None
    status: Optional[AppointmentStatus] = None
    booking_source: Optional[BookingSource] = None

    @model_validator(mode="after")
    def end_after_start(self):
        if self.start_datetime is not None and self.end_datetime is not None and self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self


class AppointmentInDBBase(AppointmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: AppointmentStatus
    duration_minutes: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    # AI/ML fields (optional in response)
    predicted_duration: Optional[int] = None
    predicted_no_show_probability: Optional[float] = None
    predicted_waiting_time: Optional[int] = None
    recommendation_score: Optional[float] = None
    # Convenience display fields for dashboards (populated by
    # appointment_service.to_appointment_read; not auto-derived from the ORM
    # object by Pydantic, since they require traversing doctor.user/patient.user).
    doctor_name: Optional[str] = None
    patient_name: Optional[str] = None
    specialization_name: Optional[str] = None


class AppointmentRead(AppointmentInDBBase):
    """Response schema. Named distinctly from the `Appointment` ORM model
    (app.models.appointment.Appointment) to avoid the name collision that
    previously made `from app.schemas.appointment import Appointment` shadow
    the ORM class wherever both were imported."""

    pass
