import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AppointmentStatus, AppointmentType, BookingSource


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        # First line of defense against double-booking: no two appointments for the
        # same doctor can start at the exact same instant. This alone does not catch
        # overlapping-but-different-start-time conflicts — that is enforced in
        # app/services/appointment_service.py via a row lock + range check inside a
        # single DB transaction (see Phase 3 / SCHEDULING.md).
        UniqueConstraint("doctor_id", "start_datetime", name="uq_doctor_start_time"),
        Index("ix_doctor_time_range", "doctor_id", "start_datetime", "end_datetime"),
        CheckConstraint("end_datetime > start_datetime", name="ck_appointment_end_after_start"),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0", name="ck_appointment_duration_positive"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    specialization_id: Mapped[int] = mapped_column(ForeignKey("specializations.id"), nullable=False)

    start_datetime: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_datetime: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)

    appointment_type: Mapped[AppointmentType] = mapped_column(
        Enum(AppointmentType), nullable=False, default=AppointmentType.consultation
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.scheduled, index=True
    )
    booking_source: Mapped[BookingSource] = mapped_column(
        Enum(BookingSource), nullable=False, default=BookingSource.normal
    )

    # Actual (ground-truth) duration of the appointment in minutes. Populated from
    # start/end at creation time and can be corrected when the appointment is marked
    # completed. This is the real value used as the ML "duration" training target —
    # NOT to be confused with predicted_duration below, which is a model output.
    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)

    # Time the patient actually checked in / was seen, if the clinic records it.
    # Used only to compute a deterministic waiting-time *estimate*; there is no
    # trained waiting-time model (see ML_STATUS.md) because we don't have a
    # non-circular ground-truth waiting time signal.
    checked_in_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    # AI/ML-derived fields, stored for auditability & to power dashboards.
    predicted_duration: Mapped[int | None] = mapped_column(nullable=True)  # minutes
    predicted_no_show_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_waiting_time: Mapped[int | None] = mapped_column(nullable=True)  # minutes
    recommendation_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    patient: Mapped["Patient"] = relationship(back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship(back_populates="appointments")
    specialization: Mapped["Specialization"] = relationship()
    notifications: Mapped[list["Notification"]] = relationship(back_populates="appointment")
