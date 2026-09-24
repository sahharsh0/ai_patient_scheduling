"""
Recommendation engine: ranks real, available candidate slots for one or more
doctors using ML predictions (duration, no-show) plus a deterministic
waiting-time estimate, combined with the patient's stated preferences
(experience_preference, wait_preference, time_of_day) from the AI parser.

This is the piece that makes the AI flow genuinely "embedded" rather than
decorative: the LLM's parsed output feeds directly into which doctors/slots
get considered and how they're scored — see app/api/ai.py.
"""
import datetime as dt
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.ai.grounding import resolve_time_of_day_window
from app.ml.service import get_doctor_historical_stats, get_patient_historical_stats, predict_appointment
from app.models.doctor import Doctor
from app.scheduling.slots import CandidateSlot, generate_available_slots
from app.services.prediction_log_service import log_prediction

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {"duration": 0.2, "noshow": 0.4, "waiting": 0.2, "preference_match": 0.2}
MAX_WAITING_TIME = 60.0


def _duration_score(predicted_duration: float, preferred_duration: Optional[float]) -> float:
    if preferred_duration and preferred_duration > 0:
        diff = abs(predicted_duration - preferred_duration)
        return max(0.0, 1.0 - diff / max(preferred_duration, 1.0))
    if predicted_duration <= 30.0:
        return 1.0
    if predicted_duration >= 120.0:
        return 0.0
    return 1.0 - (predicted_duration - 30.0) / 90.0


def _preference_match_score(
    slot: CandidateSlot, doctor: Doctor, time_of_day: Optional[str], experience_preference: Optional[str]
) -> float:
    score = 1.0
    if time_of_day:
        window_start, window_end = resolve_time_of_day_window(time_of_day)
        if not (window_start <= slot.start_datetime.time() <= window_end):
            score -= 0.5
    if experience_preference == "high":
        # Normalize experience against a reasonable career span (30 years).
        score = score * 0.5 + 0.5 * min((doctor.experience_years or 0) / 30.0, 1.0)
    return max(0.0, min(1.0, score))


def _explain(
    predicted_duration: float,
    no_show_prob: float,
    waiting_time: float,
    slot: CandidateSlot,
    time_of_day: Optional[str],
    experience_preference: Optional[str],
    doctor: Doctor,
) -> List[str]:
    """Every line here states a factor that was actually computed above —
    no invented facts."""
    explanations = []
    if time_of_day:
        window_start, window_end = resolve_time_of_day_window(time_of_day)
        if window_start <= slot.start_datetime.time() <= window_end:
            explanations.append(f"Matches your requested {time_of_day} time preference.")
    if experience_preference == "high" and (doctor.experience_years or 0) >= 10:
        explanations.append(f"Doctor has {doctor.experience_years} years of experience.")
    if no_show_prob < 0.1:
        explanations.append(f"Low estimated no-show probability ({no_show_prob * 100:.0f}%).")
    elif no_show_prob >= 0.3:
        explanations.append(f"Higher estimated no-show probability ({no_show_prob * 100:.0f}%).")
    if waiting_time <= 5:
        explanations.append("Minimal estimated wait time.")
    elif waiting_time >= 20:
        explanations.append(f"Estimated wait time is longer (~{waiting_time:.0f} min).")
    explanations.append(f"Predicted visit length: ~{predicted_duration:.0f} min.")
    return explanations


def compute_slot_score(
    predicted_duration_minutes: float,
    no_show_probability: float,
    waiting_time_minutes: float,
    preference_score: float = 1.0,
    wait_preference: Optional[str] = None,
    preferred_duration: Optional[float] = None,
) -> float:
    """
    Shared scoring formula used both to RANK candidate slots
    (recommend_candidates, below) and to record a recommendation_score for
    whichever slot actually gets booked (app/services/appointment_service.py
    -> create_appointment), so a manually-booked appointment gets the same
    honestly-computed score as an AI-recommended one instead of being left
    NULL. preference_score defaults to 1.0 (neutral) for manual bookings,
    which have no stated time-of-day/experience preference to match against.
    """
    weights = dict(DEFAULT_WEIGHTS)
    if wait_preference == "low":
        weights["waiting"] += 0.15
        weights["noshow"] -= 0.075
        weights["duration"] -= 0.075

    duration_score = _duration_score(predicted_duration_minutes, preferred_duration)
    noshow_score = 1.0 - no_show_probability
    waiting_score = 1.0 - min(waiting_time_minutes / MAX_WAITING_TIME, 1.0)

    total_score = (
        weights["duration"] * duration_score
        + weights["noshow"] * noshow_score
        + weights["waiting"] * waiting_score
        + weights["preference_match"] * preference_score
    )
    return round(float(total_score), 4)


def recommend_candidates(
    db: Session,
    doctors: List[Doctor],
    preferred_date: dt.date,
    patient_id: Optional[int] = None,
    time_of_day: Optional[str] = None,
    experience_preference: Optional[str] = None,
    wait_preference: Optional[str] = None,
    appointment_type: str = "consultation",
    booking_source: str = "ai",
    max_candidates: int = 5,
    search_days_ahead: int = 7,
) -> List[Dict[str, Any]]:
    """
    Generate and rank real available appointment slots.

    Explicit user constraints are treated as hard filters:
      - preferred_date -> only that calendar date
      - time_of_day -> only slots inside that time window

    Other preferences such as doctor experience and waiting time are used
    for ranking valid slots.

    The engine never silently changes the requested date or time.
    """

    patient_historical = (
        get_patient_historical_stats(db, patient_id)
        if patient_id
        else None
    )

    scored: List[Dict[str, Any]] = []

    # Convert the requested time of day into a concrete clock-time window.
    time_window = None
    if time_of_day:
        time_window = resolve_time_of_day_window(time_of_day)

    for doctor in doctors:
        doctor_historical = get_doctor_historical_stats(db, doctor.id)

        # IMPORTANT:
        # preferred_date is an explicit user constraint.
        # Do not search future dates automatically.
        target_date = preferred_date

        slots = generate_available_slots(
            db,
            doctor.id,
            target_date,
        )

        if not slots:
            continue

        for slot in slots:

            # ---------------------------------------------------------
            # HARD FILTER 1: exact requested date
            # ---------------------------------------------------------
            if slot.start_datetime.date() != preferred_date:
                continue

            # ---------------------------------------------------------
            # HARD FILTER 2: requested time of day
            # ---------------------------------------------------------
            if time_window is not None:
                window_start, window_end = time_window
                slot_time = slot.start_datetime.time()

                if not (
                    window_start
                    <= slot_time
                    <= window_end
                ):
                    continue

            # ---------------------------------------------------------
            # ML predictions only happen for valid candidate slots.
            # ---------------------------------------------------------
            predictions = predict_appointment(
                db,
                doctor_id=doctor.id,
                patient_id=patient_id,
                appointment_datetime=slot.start_datetime,
                appointment_type=appointment_type,
                booking_source=booking_source,
                specialization_id=doctor.specialization_id,
                doctor_historical=doctor_historical,
                patient_historical=patient_historical,
            )

            log_prediction(
                db,
                prediction_type="appointment_slot_recommendation",
                input_features={
                    "doctor_id": doctor.id,
                    "slot_start": slot.start_datetime.isoformat(),
                    "appointment_type": appointment_type,
                    "booking_source": booking_source,
                },
                prediction=predictions,
                model_version=predictions.get(
                    "model_version",
                    "unknown",
                ),
            )

            # ---------------------------------------------------------
            # Preference scoring
            #
            # At this point time_of_day is already guaranteed to match,
            # so preference scoring can focus on ranking quality.
            # ---------------------------------------------------------
            preference_score = _preference_match_score(
                slot,
                doctor,
                time_of_day,
                experience_preference,
            )

            total_score = compute_slot_score(
                predictions["duration_minutes"],
                predictions["no_show_probability"],
                predictions["waiting_time_minutes"],
                preference_score=preference_score,
                wait_preference=wait_preference,
            )

            explanations = _explain(
                predictions["duration_minutes"],
                predictions["no_show_probability"],
                predictions["waiting_time_minutes"],
                slot,
                time_of_day,
                experience_preference,
                doctor,
            )

            scored.append(
                {
                    "doctor": doctor,
                    "slot": slot,
                    "score": round(float(total_score), 4),
                    "predicted_duration_minutes": round(
                        predictions["duration_minutes"],
                        1,
                    ),
                    "predicted_no_show_probability": round(
                        predictions["no_show_probability"],
                        3,
                    ),
                    "predicted_waiting_time_minutes": predictions[
                        "waiting_time_minutes"
                    ],
                    "explanations": explanations,
                }
            )

    # Highest quality valid slots first.
    scored.sort(
        key=lambda candidate: candidate["score"],
        reverse=True,
    )

    return scored[:max_candidates]