"""
Appointment scheduling engine.

Booking and rescheduling both go through `_validate_and_lock`, which:
  1. Locks the doctor row (SELECT ... FOR UPDATE) so concurrent booking
     attempts for the SAME doctor are serialized by the database.
  2. Re-validates doctor existence, specialization match, availability,
     leave, and overlap conflicts *inside that lock* — a "time-of-check to
     time-of-use" race is exactly what the lock exists to close.
  3. Lets IntegrityError (e.g. the (doctor_id, start_datetime) unique
     constraint) surface as a clean 409 rather than a raw 500.

Two appointments conflict when `existing.start < requested.end AND
existing.end > requested.start` — a genuine interval overlap, not just an
equal-start-time check.
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus
from app.models.patient import Patient
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentUpdate
from app.scheduling.slots import (
    doctor_leave_overlaps,
    fits_within_availability,
    get_conflicting_appointment,
)
from app.services.notification_service import (
    notify_appointment_booked,
    notify_appointment_cancelled,
    notify_appointment_rescheduled,
)
from app.services.waitlist_service import notify_matching_waitlist_entries
from app.ml.service import predict_appointment
from app.services.recommendation_service import compute_slot_score
from app.services.prediction_log_service import log_prediction

logger = logging.getLogger(__name__)


def _validate_and_lock(
    db: Session,
    doctor_id: int,
    specialization_id: int,
    start_datetime: datetime,
    end_datetime: datetime,
    exclude_appointment_id: Optional[int] = None,
) -> Doctor:
    """
    Lock the doctor row and run every scheduling check against the live,
    locked state of the database. Raises HTTPException on any failure.
    Returns the locked Doctor row on success.
    """
    # Lock the doctor row first: any other transaction trying to book this
    # doctor blocks here until we commit or roll back, which serializes
    # concurrent booking attempts for the same doctor.
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).with_for_update().first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    if doctor.specialization_id != specialization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specialization does not match doctor's specialization",
        )

    if end_datetime <= start_datetime:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End datetime must be after start datetime")

    if not fits_within_availability(db, doctor_id, start_datetime, end_datetime):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The requested time does not fit within the doctor's working hours",
        )

    if doctor_leave_overlaps(db, doctor_id, start_datetime, end_datetime):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The requested time falls within the doctor's leave period"
        )

    conflicting = get_conflicting_appointment(
        db, doctor_id, start_datetime, end_datetime, exclude_appointment_id=exclude_appointment_id, lock=True
    )
    if conflicting:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The requested time slot is already booked")

    return doctor


def create_appointment(db: Session, appointment_in: AppointmentCreate) -> Appointment:
    """Create a new appointment with full scheduling engine checks, inside a single transaction."""
    patient = db.get(Patient, appointment_in.patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    try:
        _validate_and_lock(
            db,
            doctor_id=appointment_in.doctor_id,
            specialization_id=appointment_in.specialization_id,
            start_datetime=appointment_in.start_datetime,
            end_datetime=appointment_in.end_datetime,
        )

        duration_minutes = int((appointment_in.end_datetime - appointment_in.start_datetime).total_seconds() // 60)

        # Compute the same ML predictions + recommendation score used to
        # rank AI-recommended slots, and store them on the row itself
        # (predicted_duration / predicted_no_show_probability /
        # predicted_waiting_time / recommendation_score). This runs for
        # EVERY booking — manual or AI — not just AI recommendations, so
        # those columns are never silently left NULL on a real booking, and
        # the historical stats used at future prediction time stay accurate.
        # Prediction failures must never block a booking, so any error here
        # is logged and the appointment is still created with NULL
        # prediction fields rather than failing the whole request.
        predicted_duration = predicted_no_show = predicted_waiting = recommendation_score = None
        predictions = None
        try:
            predictions = predict_appointment(
                db,
                doctor_id=appointment_in.doctor_id,
                patient_id=appointment_in.patient_id,
                appointment_datetime=appointment_in.start_datetime,
                appointment_type=appointment_in.appointment_type,
                booking_source=appointment_in.booking_source,
                specialization_id=appointment_in.specialization_id,
            )
            predicted_duration = round(predictions["duration_minutes"])
            predicted_no_show = predictions["no_show_probability"]
            predicted_waiting = round(predictions["waiting_time_minutes"])
            recommendation_score = compute_slot_score(
                predictions["duration_minutes"],
                predictions["no_show_probability"],
                predictions["waiting_time_minutes"],
            )
        except Exception:
            logger.exception("Failed to compute ML predictions for a new appointment — booking without them.")

        appointment = Appointment(
            **appointment_in.dict(),
            status=AppointmentStatus.scheduled,
            duration_minutes=duration_minutes,
            predicted_duration=predicted_duration,
            predicted_no_show_probability=predicted_no_show,
            predicted_waiting_time=predicted_waiting,
            recommendation_score=recommendation_score,
        )
        db.add(appointment)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The requested time slot is already booked")
    except HTTPException:
        db.rollback()
        raise
    db.refresh(appointment)
    notify_appointment_booked(db, appointment)

    # Log the prediction AFTER the booking transaction has fully committed:
    # log_prediction() does its own commit/rollback, and running it before
    # the appointment commit would prematurely release the doctor-row lock
    # taken in _validate_and_lock, reopening the exact race condition that
    # lock exists to prevent.
    if predictions is not None:
        log_prediction(
            db,
            prediction_type="appointment_booking",
            input_features={
                "doctor_id": appointment.doctor_id,
                "appointment_id": appointment.id,
                "start_datetime": appointment.start_datetime.isoformat(),
                "appointment_type": str(appointment.appointment_type),
                "booking_source": str(appointment.booking_source),
            },
            prediction=predictions,
            model_version=predictions.get("model_version", "unknown"),
        )

    return appointment


def get_appointment(db: Session, appointment_id: int, current_user: User) -> Optional[Appointment]:
    """Get an appointment by ID, checking permissions based on the current user."""
    appointment = (
        db.query(Appointment)
        .options(
            joinedload(Appointment.doctor).joinedload(Doctor.user),
            joinedload(Appointment.patient).joinedload(Patient.user),
            joinedload(Appointment.specialization),
        )
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        return None

    if current_user.role == "patient":
        if not current_user.patient or appointment.patient_id != current_user.patient.id:
            return None
    elif current_user.role == "doctor":
        if not current_user.doctor or appointment.doctor_id != current_user.doctor.id:
            return None
    # admin can see all

    return appointment


def get_appointments(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[str] = None,
    current_user: Optional[User] = None,
) -> List[Appointment]:
    """
    List appointments with optional filtering and permission checks.

    IMPORTANT: patient_id/doctor_id query params are only honored for admins.
    A patient or doctor's own appointments are always scoped to their own
    record derived from the authenticated user, never from client input —
    see GET /api/appointments/me for the identity-safe endpoint patients and
    doctors should actually use.
    """
    query = db.query(Appointment).options(
        joinedload(Appointment.doctor).joinedload(Doctor.user),
        joinedload(Appointment.patient).joinedload(Patient.user),
        joinedload(Appointment.specialization),
    )

    if current_user and current_user.role == "patient":
        if not current_user.patient:
            return []
        query = query.filter(Appointment.patient_id == current_user.patient.id)
    elif current_user and current_user.role == "doctor":
        if not current_user.doctor:
            return []
        query = query.filter(Appointment.doctor_id == current_user.doctor.id)
    else:
        # admin (or no user, for internal use): honor the filters as given.
        if patient_id:
            query = query.filter(Appointment.patient_id == patient_id)
        if doctor_id:
            query = query.filter(Appointment.doctor_id == doctor_id)

    if start_date:
        query = query.filter(Appointment.start_datetime >= start_date)
    if end_date:
        query = query.filter(Appointment.start_datetime <= end_date)
    if status:
        query = query.filter(Appointment.status == status)

    return query.order_by(Appointment.start_datetime.desc()).offset(skip).limit(limit).all()


def update_appointment(
    db: Session, appointment_id: int, appointment_in: AppointmentUpdate, current_user: User
) -> Optional[Appointment]:
    """Reschedule an existing appointment, re-running every scheduling check inside the lock."""
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        return None

    if current_user.role != "patient" or not current_user.patient or appointment.patient_id != current_user.patient.id:
        return None

    if appointment.status != AppointmentStatus.scheduled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only scheduled appointments can be rescheduled")

    update_data = appointment_in.dict(exclude_unset=True)

    try:
        if "start_datetime" in update_data or "end_datetime" in update_data:
            start_dt = update_data.get("start_datetime", appointment.start_datetime)
            end_dt = update_data.get("end_datetime", appointment.end_datetime)

            _validate_and_lock(
                db,
                doctor_id=appointment.doctor_id,
                specialization_id=appointment.specialization_id,
                start_datetime=start_dt,
                end_datetime=end_dt,
                exclude_appointment_id=appointment_id,
            )
            update_data["duration_minutes"] = int((end_dt - start_dt).total_seconds() // 60)

        for field, value in update_data.items():
            setattr(appointment, field, value)

        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The requested time slot is already booked")
    except HTTPException:
        db.rollback()
        raise
    db.refresh(appointment)
    notify_appointment_rescheduled(db, appointment)
    return appointment


def cancel_appointment(db: Session, appointment_id: int, current_user: User) -> bool:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        return False

    if current_user.role != "patient" or not current_user.patient or appointment.patient_id != current_user.patient.id:
        return False

    if appointment.status != AppointmentStatus.scheduled:
        return False

    appointment.status = AppointmentStatus.cancelled
    db.commit()
    notify_appointment_cancelled(db, appointment)
    notify_matching_waitlist_entries(db, appointment.specialization_id, appointment.start_datetime)
    return True


def to_appointment_read(appointment: Appointment) -> AppointmentRead:
    """
    Build the API response from an Appointment, filling in the convenience
    display fields (doctor_name, patient_name, specialization_name) from the
    already-loaded relationships. Used by every appointments.py endpoint so
    dashboards show a name instead of a bare doctor_id/patient_id.
    """
    data = AppointmentRead.model_validate(appointment)
    if appointment.doctor and appointment.doctor.user:
        data.doctor_name = appointment.doctor.user.name
    if appointment.patient and appointment.patient.user:
        data.patient_name = appointment.patient.user.name
    if appointment.specialization:
        data.specialization_name = appointment.specialization.name
    return data
