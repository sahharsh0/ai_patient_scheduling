
"""
Natural-language -> ParsedAppointmentRequest.

Uses NVIDIA NIM through its OpenAI-compatible API.

The AI receives:
1. The real current date.
2. The real specialization names from the database.
3. The patient's natural-language request.

The model returns structured appointment information through
tool/function calling.

The backend validates the result and resolves it against the
real database. The AI never directly books an appointment.
"""

import datetime as dt
import json
import logging
from typing import List, Optional

from openai import OpenAI
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.ai import AIParseResponse, ParsedAppointmentRequest

logger = logging.getLogger(__name__)


_PARSE_TOOL = {
    "type": "function",
    "function": {
        "name": "record_appointment_request",
        "description": (
            "Record the structured appointment request extracted "
            "from the patient's message."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "specialization_name": {
                    "type": ["string", "null"],
                    "description": (
                        "The requested medical specialization. "
                        "Must be exactly one of the valid specialization "
                        "names provided in the system prompt, or null."
                    ),
                },
                "doctor_name": {
                    "type": ["string", "null"],
                    "description": (
                        "The specific doctor's name if the patient "
                        "requested a particular doctor, otherwise null."
                    ),
                },
                "preferred_date": {
                    "type": ["string", "null"],
                    "description": (
                        "The requested calendar date in YYYY-MM-DD format. "
                        "Resolve relative dates such as tomorrow or "
                        "next Monday using the supplied current date."
                    ),
                },
                "time_of_day": {
                    "type": ["string", "null"],
                    "enum": [
                        "morning",
                        "afternoon",
                        "evening",
                        None,
                    ],
                    "description": "Preferred time of day.",
                },
                "urgency": {
                    "type": ["string", "null"],
                    "enum": [
                        "low",
                        "normal",
                        "high",
                        None,
                    ],
                    "description": "Urgency preference.",
                },
                "experience_preference": {
                    "type": ["string", "null"],
                    "enum": [
                        "low",
                        "normal",
                        "high",
                        None,
                    ],
                    "description": (
                        "Doctor experience preference. "
                        "'high' means the patient prefers an experienced doctor."
                    ),
                },
                "wait_preference": {
                    "type": ["string", "null"],
                    "enum": [
                        "low",
                        "normal",
                        "high",
                        None,
                    ],
                    "description": (
                        "Preference regarding expected waiting time."
                    ),
                },
                "appointment_type": {
                    "type": ["string", "null"],
                    "enum": [
                        "consultation",
                        "follow_up",
                        "check_up",
                        "procedure",
                        None,
                    ],
                    "description": "Requested appointment type.",
                },
            },
            "required": [
                "specialization_name",
                "doctor_name",
                "preferred_date",
                "time_of_day",
                "urgency",
                "experience_preference",
                "wait_preference",
                "appointment_type",
            ],
        },
    },
}


def _build_system_prompt(
    today: dt.date,
    valid_specializations: List[str],
) -> str:
    specialization_lines = "\n".join(
        f"- {specialization}"
        for specialization in valid_specializations
    )

    return f"""
You are the natural-language appointment intake assistant
for SmartCare AI.

Your job is ONLY to understand the patient's appointment request
and convert it into structured information.

You do NOT book appointments.
You do NOT select database IDs.
You do NOT diagnose medical conditions.
You do NOT invent doctors or specializations.

Today's real date is:
{today.isoformat()} ({today.strftime("%A")})

Use this date to resolve relative dates.

Examples:
- "tomorrow" -> the next calendar day
- "day after tomorrow" -> two calendar days from today
- "next Monday" -> the next Monday after today

Valid medical specializations from the actual database:

{specialization_lines}

IMPORTANT:
- If the patient requests a specialization, choose ONLY from the
  exact list above.
- Never invent a specialization.
- Never return database IDs.
- If the patient names a doctor, preserve the doctor's name.
- If information is not provided, return null.
- Use "morning", "afternoon", or "evening" for time-of-day.
- Use "high" for experience preference when the patient asks for
  an experienced/senior doctor.
- Use "low", "normal", or "high" for urgency and waiting preference
  only when the patient's wording provides enough information.
- Use the exact appointment type values when identifiable:
  consultation, follow_up, check_up, procedure.

Call record_appointment_request exactly once.
""".strip()


def _clarification_fallback(
    question: str,
    missing: Optional[List[str]] = None,
) -> AIParseResponse:
    return AIParseResponse(
        status="needs_clarification",
        missing_fields=missing or ["specialty", "date"],
        clarification_question=question,
    )


def parse_appointment_request(
    natural_language: str,
    valid_specializations: List[str],
) -> AIParseResponse:
    """
    Parse a natural-language appointment request using NVIDIA NIM.

    All expected failures are converted into a
    needs_clarification response instead of propagating an
    exception to the API layer.
    """

    if settings.AI_PROVIDER.lower() != "nvidia":
        logger.error(
            "Unsupported AI provider configured: %s",
            settings.AI_PROVIDER,
        )

        return _clarification_fallback(
            "The AI booking assistant is not configured correctly. "
            "Please use the regular booking form instead."
        )

    if not settings.NVIDIA_API_KEY:
        logger.warning(
            "NVIDIA_API_KEY is not configured — AI parsing cannot run."
        )

        return _clarification_fallback(
            "The AI booking assistant isn't configured yet. "
            "Please use the regular booking form instead."
        )

    today = dt.date.today()

    system_prompt = _build_system_prompt(
        today=today,
        valid_specializations=valid_specializations,
    )

    try:
        client = OpenAI(
            api_key=settings.NVIDIA_API_KEY,
            base_url=settings.NVIDIA_BASE_URL,
        )

        response = client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": natural_language,
                },
            ],
            tools=[_PARSE_TOOL],
            tool_choice={
                "type": "function",
                "function": {
                    "name": "record_appointment_request",
                },
            },
            temperature=0,
            max_tokens=1024,
        )

    except Exception as exc:
        logger.exception(
            "NVIDIA API error while parsing appointment request: %s",
            exc,
        )

        return _clarification_fallback(
            "I'm having trouble processing that right now. "
            "Could you try again in a moment?"
        )

    try:
        message = response.choices[0].message

        if not message.tool_calls:
            logger.warning(
                "NVIDIA response contained no tool call."
            )

            return _clarification_fallback(
                "I didn't quite understand that. "
                "Could you rephrase your appointment request?"
            )

        tool_call = message.tool_calls[0]

        if tool_call.function.name != "record_appointment_request":
            logger.warning(
                "Unexpected NVIDIA tool call: %s",
                tool_call.function.name,
            )

            return _clarification_fallback(
                "I couldn't understand the appointment details. "
                "Could you rephrase your request?"
            )

        raw = json.loads(tool_call.function.arguments)

    except (IndexError, AttributeError, TypeError, ValueError) as exc:
        logger.exception(
            "Failed to parse NVIDIA tool-call response: %s",
            exc,
        )

        return _clarification_fallback(
            "I couldn't understand the appointment details. "
            "Could you rephrase your request?"
        )

    try:
        parsed = ParsedAppointmentRequest(
            specialization_name=raw.get(
                "specialization_name"
            ),
            doctor_name=raw.get(
                "doctor_name"
            ),
            preferred_date=raw.get(
                "preferred_date"
            ) or None,
            time_of_day=raw.get(
                "time_of_day"
            ),
            urgency=raw.get(
                "urgency"
            ),
            experience_preference=raw.get(
                "experience_preference"
            ),
            wait_preference=raw.get(
                "wait_preference"
            ),
            appointment_type=raw.get(
                "appointment_type"
            ),
        )

    except ValidationError as exc:
        logger.warning(
            "NVIDIA tool output failed Pydantic validation: %s",
            exc,
        )

        return _clarification_fallback(
            "I couldn't quite understand the appointment details. "
            "Could you tell me the specialty and preferred date?"
        )

    # Ground the specialization against the REAL database values.
    #
    # The LLM is allowed to understand the user's wording, but it
    # cannot introduce a specialization that doesn't exist.
    if parsed.specialization_name:
        matched_specialization = next(
            (
                specialization
                for specialization in valid_specializations
                if specialization.lower()
                == parsed.specialization_name.lower()
            ),
            None,
        )

        parsed.specialization_name = matched_specialization

    missing: List[str] = []

    # The appointment recommendation pipeline needs a specialization.
    if not parsed.specialization_name:
        missing.append("specialty")

    # The recommendation flow needs a requested date.
    if not parsed.preferred_date:
        missing.append("date")

    if missing:
        clarification_question = (
            raw.get("clarification_question")
            or (
                "Could you tell me the "
                + " and ".join(missing)
                + " you'd like for this appointment?"
            )
        )

        return AIParseResponse(
            status="needs_clarification",
            missing_fields=missing,
            clarification_question=clarification_question,
        )

    return AIParseResponse(
        status="complete",
        data=parsed,
    )
