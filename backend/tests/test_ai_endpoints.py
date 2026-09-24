"""
Integration tests for POST /api/ai/recommend. This endpoint never calls the
LLM (that's /api/ai/parse) — it's pure database grounding + the
recommendation engine — so it's tested for real, end-to-end, against the
test database, with no mocking required.
"""
import datetime as dt

from app.core.security import hash_password
from app.models import Doctor, DoctorAvailability, Specialization, User
from app.models.enums import UserRole


def _register_patient(client, email="patient@test.com"):
    resp = client.post(
        "/api/auth/register", json={"name": "Test Patient", "email": email, "password": "SecurePass123"}
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _seed_doctor(db):
    spec = Specialization(name="Cardiology", description="Heart specialist")
    db.add(spec)
    db.flush()
    user = User(name="Dr. Ananya Sharma", email="doctor@test.com", password_hash=hash_password("x"), role=UserRole.doctor)
    db.add(user)
    db.flush()
    doctor = Doctor(user_id=user.id, specialization_id=spec.id, experience_years=12, consultation_fee=100.0, rating=4.8)
    db.add(doctor)
    db.flush()
    for day in range(7):
        db.add(DoctorAvailability(doctor_id=doctor.id, day_of_week=day, start_time=dt.time(9, 0), end_time=dt.time(17, 0), slot_duration=30))
    db.commit()
    return spec, doctor


def test_recommend_unknown_specialization_asks_for_clarification(client, db):
    token = _register_patient(client)
    resp = client.post(
        "/api/ai/recommend",
        json={"specialization_name": "Podiatry", "preferred_date": (dt.date.today() + dt.timedelta(days=1)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "needs_clarification"


def test_recommend_missing_date_asks_for_clarification(client, db):
    token = _register_patient(client)
    resp = client.post(
        "/api/ai/recommend",
        json={"specialization_name": "Cardiology"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "needs_clarification"


def test_recommend_returns_real_candidates_for_valid_request(client, db):
    _seed_doctor(db)
    token = _register_patient(client)

    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    resp = client.post(
        "/api/ai/recommend",
        json={"specialization_name": "Cardiology", "preferred_date": tomorrow, "time_of_day": "morning"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert len(body["candidates"]) > 0
    candidate = body["candidates"][0]
    assert candidate["doctor_name"] == "Dr. Ananya Sharma"
    assert candidate["specialization_name"] == "Cardiology"
    assert 0.0 <= candidate["score"] <= 1.0


def test_booking_a_recommended_candidate_succeeds(client, db):
    """The end of the AI flow: the candidate the recommend endpoint returned
    must actually be bookable through the normal /api/appointments endpoint —
    proving the AI path and the manual booking path share one scheduling
    engine, not two divergent ones."""
    _seed_doctor(db)
    token = _register_patient(client)
    headers = {"Authorization": f"Bearer {token}"}

    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    recommend_resp = client.post(
        "/api/ai/recommend",
        json={"specialization_name": "Cardiology", "preferred_date": tomorrow},
        headers=headers,
    )
    candidate = recommend_resp.json()["candidates"][0]

    book_resp = client.post(
        "/api/appointments",
        json={
            "doctor_id": candidate["doctor_id"],
            "specialization_id": candidate["specialization_id"],
            "start_datetime": candidate["start_datetime"],
            "end_datetime": candidate["end_datetime"],
            "appointment_type": "consultation",
            "booking_source": "ai",
        },
        headers=headers,
    )
    assert book_resp.status_code == 201
    assert book_resp.json()["status"] == "scheduled"
