from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import AppointmentType


class ParsedAppointmentRequest(BaseModel):
    """
    Structured HUMAN requirements extracted from natural language by the LLM.

    Deliberately contains NO database primary keys (doctor_id,
    specialization_id, ...): the LLM is never asked to invent an ID. Instead
    it names concepts (a specialization name, optionally a doctor's name,
    a date, a time-of-day preference) which the backend resolves against the
    real database using ordinary SQL — see app/ai/grounding.py.
    """

    specialization_name: Optional[str] = Field(
        None, description="A specialization name, chosen from the list given in the prompt, or null"
    )
    doctor_name: Optional[str] = Field(None, description="A doctor's name if the patient asked for someone specific")
    preferred_date: Optional[date] = Field(None, description="The concrete calendar date requested, already resolved from any relative phrase like 'tomorrow'")
    time_of_day: Optional[str] = Field(None, description="One of 'morning', 'afternoon', 'evening', or null")
    urgency: Optional[str] = Field(None, description="One of 'low', 'normal', 'high', or null")
    experience_preference: Optional[str] = Field(None, description="One of 'low', 'normal', 'high' (patient wants an experienced doctor), or null")
    wait_preference: Optional[str] = Field(None, description="One of 'low' (wants minimal waiting), 'normal', 'high', or null")
    appointment_type: Optional[AppointmentType] = Field(None, description="One of the appointment type enum values, or null to default to consultation")


class AIParseResponse(BaseModel):
    """Response from the natural-language parsing stage."""

    status: str = Field(..., description="'complete' or 'needs_clarification'")
    data: Optional[ParsedAppointmentRequest] = None
    missing_fields: Optional[List[str]] = None
    clarification_question: Optional[str] = None


class RecommendedSlot(BaseModel):
    """
    A single ranked, bookable candidate. Every field here was actually
    computed by the recommendation pipeline (database grounding + ML/
    deterministic predictions) — nothing is invented by the LLM.
    """

    doctor_id: int
    doctor_name: str
    specialization_id: int
    specialization_name: str
    start_datetime: str
    end_datetime: str
    score: float
    predicted_duration_minutes: Optional[float] = None
    predicted_no_show_probability: Optional[float] = None
    predicted_waiting_time_minutes: Optional[float] = None
    explanations: List[str] = Field(default_factory=list)


class AIRecommendationResponse(BaseModel):
    status: str = Field(..., description="'complete', 'needs_clarification', or 'no_availability'")
    clarification_question: Optional[str] = None
    missing_fields: Optional[List[str]] = None
    parsed: Optional[ParsedAppointmentRequest] = None
    specialization_id: Optional[int] = Field(
        None, description="Resolved specialization id, included on 'no_availability' so the client can offer to join the waitlist without re-resolving the name."
    )
    preferred_date: Optional[str] = None
    candidates: List[RecommendedSlot] = Field(default_factory=list)

# Note: there is deliberately no separate "confirm booking" schema/endpoint
# here. Once the patient picks a RecommendedSlot candidate above, the
# frontend books it through the exact same POST /api/appointments path (and
# app.services.appointment_service.create_appointment) used for a manual
# booking — see app/api/appointments.py and frontend/app/ai-book/page.tsx.
# That keeps exactly one code path responsible for validating and persisting
# a booking (locking, availability/leave/overlap checks, and now storing the
# ML predictions on the row) instead of two parallel ones to keep in sync.
