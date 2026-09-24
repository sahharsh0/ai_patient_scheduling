import datetime as dt
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.ai.grounding import (
    find_candidate_doctors,
    list_specialization_names,
    resolve_doctor_by_name,
    resolve_specialization,
)
from app.ai.service import parse_appointment_request
from app.models.user import User
from app.schemas.ai import AIParseResponse, AIRecommendationResponse, RecommendedSlot
from app.services.recommendation_service import recommend_candidates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/parse", response_model=AIParseResponse)
def parse_appointment_endpoint(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stage 1 of the AI flow: natural language -> ParsedAppointmentRequest.
    The LLM never sees or invents a doctor_id/specialization_id — see
    app/ai/service.py and app/schemas/ai.ParsedAppointmentRequest.
    """
    natural_language = payload.get("text")
    if not natural_language or not isinstance(natural_language, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing or invalid 'text' field in request body")

    valid_specializations = list_specialization_names(db)
    return parse_appointment_request(natural_language, valid_specializations)


@router.post("/recommend", response_model=AIRecommendationResponse)
def recommend_endpoint(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stage 2 of the AI flow: database grounding + candidate retrieval + ML
    ranking. Takes the ParsedAppointmentRequest fields (as produced by
    /api/ai/parse) and returns real, bookable candidate slots. The LLM has no
    involvement past this point — everything here is SQL + the scheduling
    engine + the ML/recommendation models.
    """
    specialization_name = payload.get("specialization_name")
    doctor_name = payload.get("doctor_name")
    preferred_date_str = payload.get("preferred_date")
    time_of_day = payload.get("time_of_day")
    experience_preference = payload.get("experience_preference")
    wait_preference = payload.get("wait_preference")
    appointment_type = payload.get("appointment_type") or "consultation"

    specialization = resolve_specialization(db, specialization_name)
    if specialization_name and not specialization:
        return AIRecommendationResponse(
            status="needs_clarification",
            missing_fields=["specialty"],
            clarification_question=f"I don't have a specialty matching '{specialization_name}'. Which specialty would you like to book?",
        )

    if not preferred_date_str:
        return AIRecommendationResponse(
            status="needs_clarification", missing_fields=["date"], clarification_question="What day would you prefer?"
        )
    try:
        preferred_date = dt.date.fromisoformat(preferred_date_str)
    except ValueError:
        return AIRecommendationResponse(
            status="needs_clarification", missing_fields=["date"], clarification_question="I couldn't understand that date — could you give me a specific day?"
        )

    doctor = resolve_doctor_by_name(db, doctor_name, specialization.id if specialization else None)
    doctors = find_candidate_doctors(
        db, specialization_id=specialization.id if specialization else None, doctor_id=doctor.id if doctor else None
    )

    if not doctors:
        if doctor_name and not doctor:
            return AIRecommendationResponse(
                status="needs_clarification",
                missing_fields=["doctor"],
                clarification_question=f"I couldn't find a doctor named '{doctor_name}'. Would you like to see any available doctor instead?",
            )
        return AIRecommendationResponse(
            status="needs_clarification",
            missing_fields=["specialty"],
            clarification_question="Which specialty would you like to book?",
        )

    patient_id = current_user.patient.id if current_user.role == "patient" and current_user.patient else None

    ranked = recommend_candidates(
        db,
        doctors=doctors,
        preferred_date=preferred_date,
        patient_id=patient_id,
        time_of_day=time_of_day,
        experience_preference=experience_preference,
        wait_preference=wait_preference,
        appointment_type=appointment_type,
        booking_source="ai",
    )

    if not ranked:
        return AIRecommendationResponse(
            status="no_availability",
            specialization_id=specialization.id if specialization else None,
            preferred_date=preferred_date.isoformat(),
            clarification_question=(
                f"I couldn't find any open "
                f"{time_of_day + ' ' if time_of_day else ''}"
                f"slots for {preferred_date.strftime('%B')} "
                f"{preferred_date.day}, {preferred_date.year}. "
                "Would you like to try a different date or time, "
                "or join the waitlist?"
            ),
        )

    candidates = [
        RecommendedSlot(
            doctor_id=c["doctor"].id,
            doctor_name=c["doctor"].user.name if c["doctor"].user else "Unknown",
            specialization_id=c["doctor"].specialization_id,
            specialization_name=c["doctor"].specialization.name if c["doctor"].specialization else "",
            start_datetime=c["slot"].start_datetime.isoformat(),
            end_datetime=c["slot"].end_datetime.isoformat(),
            score=c["score"],
            predicted_duration_minutes=c["predicted_duration_minutes"],
            predicted_no_show_probability=c["predicted_no_show_probability"],
            predicted_waiting_time_minutes=c["predicted_waiting_time_minutes"],
            explanations=c["explanations"],
        )
        for c in ranked
    ]

    return AIRecommendationResponse(status="complete", candidates=candidates)
