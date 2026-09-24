"""
Integration tests for app/services/recommendation_service.py:
recommend_candidates() should find real, available slots for real doctors
and rank them using the ML/heuristic predictions — end to end, against the
test database (not mocked out), since that's the only way to verify the
candidates it returns are actually bookable.
"""
import datetime as dt

from app.core.security import hash_password
from app.models import Doctor, DoctorAvailability, Patient, Specialization, User
from app.models.enums import UserRole
from app.services.recommendation_service import recommend_candidates


def _make_doctor(db, name="Dr. Test", experience_years=10):
    spec = db.query(Specialization).filter_by(name="Cardiology").first()
    if not spec:
        spec = Specialization(name="Cardiology", description="Heart specialist")
        db.add(spec)
        db.flush()

    user = User(name=name, email=f"{name.lower().replace(' ', '.')}@test.com", password_hash=hash_password("SecurePass123"), role=UserRole.doctor)
    db.add(user)
    db.flush()
    doctor = Doctor(user_id=user.id, specialization_id=spec.id, experience_years=experience_years, consultation_fee=100.0, rating=4.5)
    db.add(doctor)
    db.flush()

    for day in range(7):
        db.add(DoctorAvailability(doctor_id=doctor.id, day_of_week=day, start_time=dt.time(9, 0), end_time=dt.time(17, 0), slot_duration=30))
    db.commit()
    return spec, doctor


def _make_patient(db):
    user = User(name="Patient Jane", email="patient@test.com", password_hash=hash_password("SecurePass123"), role=UserRole.patient)
    db.add(user)
    db.flush()
    patient = Patient(user_id=user.id, date_of_birth=dt.date(1990, 1, 1), phone="9876543210")
    db.add(patient)
    db.commit()
    return patient


def test_recommend_candidates_returns_real_bookable_slots(db):
    spec, doctor = _make_doctor(db)
    patient = _make_patient(db)
    tomorrow = dt.date.today() + dt.timedelta(days=1)

    results = recommend_candidates(
        db,
        doctors=[doctor],
        preferred_date=tomorrow,
        patient_id=patient.id,
        max_candidates=5,
    )

    assert len(results) > 0
    top = results[0]
    assert 0.0 <= top["score"] <= 1.0
    assert top["predicted_duration_minutes"] > 0
    assert 0.0 <= top["predicted_no_show_probability"] <= 1.0
    assert top["predicted_waiting_time_minutes"] >= 0.0
    assert isinstance(top["explanations"], list)
    # Every candidate must be a slot that fits inside the availability window
    # we set up (09:00-17:00) — not an arbitrary/invented time.
    assert dt.time(9, 0) <= top["slot"].start_datetime.time() <= dt.time(17, 0)


def test_recommend_candidates_empty_when_doctor_has_no_availability(db):
    spec = Specialization(name="Dermatology", description="Skin specialist")
    db.add(spec)
    db.flush()
    user = User(name="Dr. NoSlots", email="noslots@test.com", password_hash=hash_password("SecurePass123"), role=UserRole.doctor)
    db.add(user)
    db.flush()
    doctor = Doctor(user_id=user.id, specialization_id=spec.id, experience_years=5, consultation_fee=80.0, rating=4.0)
    db.add(doctor)
    db.commit()
    # No DoctorAvailability rows at all for this doctor.

    tomorrow = dt.date.today() + dt.timedelta(days=1)
    results = recommend_candidates(db, doctors=[doctor], preferred_date=tomorrow, search_days_ahead=1)
    assert results == []
