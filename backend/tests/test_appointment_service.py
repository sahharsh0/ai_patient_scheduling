"""
Tests for the appointment scheduling engine (app/services/appointment_service.py
+ app/scheduling/slots.py): overlap detection, availability-window fit, leave
conflicts, and cancellation. Uses the `db` fixture (a raw session against the
same test schema `client` talks to) to set up doctors/patients directly,
since there's no public API for creating a doctor account.
"""
import datetime as dt

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.models import Doctor, DoctorAvailability, Patient, Specialization, User
from app.models.enums import UserRole
from app.schemas.appointment import AppointmentCreate
from app.services.appointment_service import cancel_appointment, create_appointment


def _make_doctor_and_patient(db):
    spec = Specialization(name="Cardiology", description="Heart specialist")
    db.add(spec)
    db.flush()

    doctor_user = User(name="Dr. Test", email="doctor@test.com", password_hash=hash_password("SecurePass123"), role=UserRole.doctor)
    db.add(doctor_user)
    db.flush()
    doctor = Doctor(user_id=doctor_user.id, specialization_id=spec.id, experience_years=10, consultation_fee=100.0, rating=4.5)
    db.add(doctor)
    db.flush()

    # Available every day of the week, 09:00-17:00, 30-minute slots — simple
    # and predictable for tests regardless of which weekday "now" falls on.
    for day in range(7):
        db.add(DoctorAvailability(doctor_id=doctor.id, day_of_week=day, start_time=dt.time(9, 0), end_time=dt.time(17, 0), slot_duration=30))

    patient_user = User(name="Patient Jane", email="patient@test.com", password_hash=hash_password("SecurePass123"), role=UserRole.patient)
    db.add(patient_user)
    db.flush()
    patient = Patient(user_id=patient_user.id, date_of_birth=dt.date(1990, 1, 1), phone="9876543210")
    db.add(patient)

    db.commit()
    return spec, doctor, patient


def _next_weekday_at(hour: int, minute: int = 0) -> dt.datetime:
    """A datetime tomorrow at the given time, safely inside the 09:00-17:00
    availability window set up above."""
    tomorrow = dt.date.today() + dt.timedelta(days=1)
    return dt.datetime.combine(tomorrow, dt.time(hour, minute))


def test_create_appointment_success(db):
    spec, doctor, patient = _make_doctor_and_patient(db)
    start = _next_weekday_at(10)

    appt_in = AppointmentCreate(
        patient_id=patient.id,
        doctor_id=doctor.id,
        specialization_id=spec.id,
        start_datetime=start,
        end_datetime=start + dt.timedelta(minutes=30),
    )
    appointment = create_appointment(db, appt_in)

    assert appointment.id is not None
    assert appointment.status.value == "scheduled"
    assert appointment.duration_minutes == 30


def test_create_appointment_doctor_not_found(db):
    spec, doctor, patient = _make_doctor_and_patient(db)
    start = _next_weekday_at(10)

    appt_in = AppointmentCreate(
        patient_id=patient.id,
        doctor_id=doctor.id + 999,  # does not exist
        specialization_id=spec.id,
        start_datetime=start,
        end_datetime=start + dt.timedelta(minutes=30),
    )
    with pytest.raises(HTTPException) as exc_info:
        create_appointment(db, appt_in)
    assert exc_info.value.status_code == 404


def test_create_appointment_outside_availability_rejected(db):
    """08:00 is before the 09:00-17:00 availability window."""
    spec, doctor, patient = _make_doctor_and_patient(db)
    start = _next_weekday_at(8)

    appt_in = AppointmentCreate(
        patient_id=patient.id,
        doctor_id=doctor.id,
        specialization_id=spec.id,
        start_datetime=start,
        end_datetime=start + dt.timedelta(minutes=30),
    )
    with pytest.raises(HTTPException) as exc_info:
        create_appointment(db, appt_in)
    assert exc_info.value.status_code == 400


def test_create_appointment_conflict_detected_on_partial_overlap(db):
    """
    The core double-booking regression test: a 10:00-10:45 appointment and a
    10:30-11:00 appointment have DIFFERENT start times but genuinely overlap,
    and must be rejected — this is exactly the case a naive
    UNIQUE(doctor_id, start_datetime) constraint misses.
    """
    spec, doctor, patient = _make_doctor_and_patient(db)
    first_start = _next_weekday_at(10, 0)

    first_in = AppointmentCreate(
        patient_id=patient.id,
        doctor_id=doctor.id,
        specialization_id=spec.id,
        start_datetime=first_start,
        end_datetime=first_start + dt.timedelta(minutes=45),
    )
    create_appointment(db, first_in)

    second_start = _next_weekday_at(10, 30)
    second_in = AppointmentCreate(
        patient_id=patient.id,
        doctor_id=doctor.id,
        specialization_id=spec.id,
        start_datetime=second_start,
        end_datetime=second_start + dt.timedelta(minutes=30),
    )
    with pytest.raises(HTTPException) as exc_info:
        create_appointment(db, second_in)
    assert exc_info.value.status_code == 409


def test_create_appointment_no_conflict_when_adjacent(db):
    """Back-to-back appointments (one ends exactly when the next starts) do
    NOT conflict — the overlap check is a half-open interval."""
    spec, doctor, patient = _make_doctor_and_patient(db)
    first_start = _next_weekday_at(10, 0)

    first_in = AppointmentCreate(
        patient_id=patient.id, doctor_id=doctor.id, specialization_id=spec.id,
        start_datetime=first_start, end_datetime=first_start + dt.timedelta(minutes=30),
    )
    create_appointment(db, first_in)

    second_in = AppointmentCreate(
        patient_id=patient.id, doctor_id=doctor.id, specialization_id=spec.id,
        start_datetime=first_start + dt.timedelta(minutes=30),
        end_datetime=first_start + dt.timedelta(minutes=60),
    )
    appointment = create_appointment(db, second_in)
    assert appointment.id is not None


def test_cancel_appointment_frees_the_slot(db):
    spec, doctor, patient = _make_doctor_and_patient(db)
    start = _next_weekday_at(10)

    appt_in = AppointmentCreate(
        patient_id=patient.id, doctor_id=doctor.id, specialization_id=spec.id,
        start_datetime=start, end_datetime=start + dt.timedelta(minutes=30),
    )
    appointment = create_appointment(db, appt_in)

    patient_user = db.get(User, patient.user_id)

    cancelled = cancel_appointment(db, appointment.id, current_user=patient_user)
    assert cancelled is True

    # Booking the exact same slot again should now succeed.
    rebooked = create_appointment(db, appt_in)
    assert rebooked.id is not None
    assert rebooked.id != appointment.id
