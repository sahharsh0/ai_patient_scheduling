"""
Natural-language -> ParsedAppointmentRequest.

Uses NVIDIA NIM through its OpenAI-compatible API.

The LLM receives:
1. The REAL current date computed by the application.
2. The REAL list of specialization names from the database.
3. The patient's natural-language appointment request.

The LLM returns structured human requirements through tool/function calling.
The backend then validates and resolves those requirements against the real
database.

The LLM is never given or asked to produce database IDs.
"""

import datetime as dt
import json
import logging
from typing import List, Optional

import openai
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.ai import AIParseResponse, ParsedAppointmentRequest

logger = logging.getLogger(__name__)


_PARSE_TOOL = {
    "name": "record_appointment_request",
    "description": (
        "Record the structured appointment request extracted from the patient's message."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "specialization_name": {
                "type": ["string", "null"],
                "description": (
                    "Must be exactly one of the provided valid specialization "
                    "names, or null if not mentioned or unclear."
                ),
            },
            "doctor_name": {
                "type": ["string", "null"],
                "description": (
                    "A specific doctor's name if requested, otherwise null."
                ),
            },
            "preferred_date": {
                "type": ["string", "null"],
                "description": (
                    "A concrete calendar date in YYYY-MM-DD format. "
                    "Resolve relative phrases such as 'today', 'tomorrow', "
                    "or 'next Monday' using the real current date provided "
                    "in the system prompt."
                ),
            },
            "time_of_day": {
                "type": ["string", "null"],
                "enum": ["morning", "afternoon", "evening", None],
            },
            "urgency": {
                "type": ["string", "null"],
                "enum": ["low", "normal", "high", None],
            },
            "experience_preference": {
                "type": ["string", "null"],
                "enum": ["low", "normal", "high", None],
            },
            "wait_preference": {
                "type": ["string", "null"],
                "enum": ["low", "normal", "high", None],
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
            },
            "missing_fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Human-facing names of essential fields that are still "
                    "missing, for example 'specialty' or 'date'. Empty when "
                    "the request contains enough information to proceed."
                ),
            },
            "clarification_question": {
                "type": ["string", "null"],
                "description": (
                    "One natural clarifying question to ask the patient if "
                    "missing_fields is non-empty. Otherwise null."
                ),
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
            "missing_fields",
            "clarification_question",
        ],
    },
}


def _build_system_prompt(
    today: dt.date,
    valid_specializations: List[str],
) -> str:
    return (
        "You are the natural-language appointment intake for a medical "
        "scheduling system.\n\n"
        f"Today's real date is {today.isoformat()} "
        f"({today.strftime('%A')}).\n\n"
        "IMPORTANT DATE RULES:\n"
        "- Resolve relative dates using ONLY today's date above.\n"
        "- 'today' means today's date.\n"
        "- 'tomorrow' means one calendar day after today's date.\n"
        "- 'day after tomorrow' means two calendar days after today's date.\n"
        "- 'next Monday', 'next Tuesday', etc. must be resolved to the "
        "appropriate upcoming calendar date.\n"
        "- preferred_date MUST be returned as YYYY-MM-DD.\n"
        "- Never return words such as 'today', 'tomorrow', or 'next Monday' "
        "in preferred_date.\n\n"
        "VALID SPECIALIZATIONS:\n"
        "Choose the closest match from this exact list, or null if none fits.\n"
        + "\n".join(f"- {s}" for s in valid_specializations)
        + "\n\n"
        "IMPORTANT RULES:\n"
        "- Never invent a specialization outside the provided list.\n"
        "- Never output database IDs.\n"
        "- Never invent a doctor name if the patient did not request one.\n"
        "- 'experienced', 'senior', or similar wording should normally map "
        "to experience_preference='high'.\n"
        "- Call record_appointment_request exactly once.\n"
    )


def _clarification_fallback(
    question: str,
    missing: Optional[List[str]] = None,
) -> AIParseResponse:
    return AIParseResponse(
        status="needs_clarification",
        missing_fields=missing or ["specialty", "date"],
        clarification_question=question,
    )


def _resolve_relative_date(
    value: Optional[str],
    today: dt.date,
) -> Optional[str]:
    """
    Defensively normalize common relative date values returned by the LLM.

    The prompt asks the LLM for YYYY-MM-DD, but this extra backend layer
    prevents values such as 'tomorrow' from reaching Pydantic unchanged.
    """

    if not value:
        return None

    value = value.strip()
    normalized = value.lower()

    if normalized == "today":
        return today.isoformat()

    if normalized == "tomorrow":
        return (today + dt.timedelta(days=1)).isoformat()

    if normalized == "day after tomorrow":
        return (today + dt.timedelta(days=2)).isoformat()

    # Already a valid ISO date.
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError:
        pass

    # Support common date formats as a defensive fallback.
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue

    # Handle weekday phrases such as "Monday" or "next Monday".
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    weekday_text = normalized.removeprefix("next ").strip()

    if weekday_text in weekdays:
        target_weekday = weekdays[weekday_text]
        days_ahead = (target_weekday - today.weekday()) % 7

        # "next Monday" should mean the next occurrence, not today.
        if normalized.startswith("next ") or days_ahead == 0:
            days_ahead = days_ahead or 7

        return (today + dt.timedelta(days=days_ahead)).isoformat()

    return None


def _parse_with_nvidia(
    natural_language: str,
    system_prompt: str,
) -> dict:
    """
    Call NVIDIA NIM using the OpenAI-compatible Chat Completions API.
    """

    if not settings.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY is not configured.")

    client = openai.OpenAI(
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
        tools=[
            {
                "type": "function",
                "function": {
                    "name": _PARSE_TOOL["name"],
                    "description": _PARSE_TOOL["description"],
                    "parameters": _PARSE_TOOL["input_schema"],
                },
            }
        ],
        tool_choice={
            "type": "function",
            "function": {
                "name": _PARSE_TOOL["name"],
            },
        },
        temperature=0,
        max_tokens=1024,
        timeout=45.0,
    )

    if not response.choices:
        raise RuntimeError("NVIDIA returned no choices.")

    message = response.choices[0].message

    if not message.tool_calls:
        raise RuntimeError("NVIDIA response contained no tool call.")

    tool_call = next(
        (
            call
            for call in message.tool_calls
            if call.function.name == _PARSE_TOOL["name"]
        ),
        None,
    )

    if tool_call is None:
        raise RuntimeError(
            "NVIDIA response did not contain the expected appointment tool call."
        )

    try:
        return json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "NVIDIA returned malformed tool-call arguments."
        ) from exc


def parse_appointment_request(
    natural_language: str,
    valid_specializations: List[str],
) -> AIParseResponse:
    """
    Parse natural language into ParsedAppointmentRequest.

    Every failure path returns needs_clarification rather than crashing
    the appointment request.
    """

    if settings.AI_PROVIDER.lower() != "nvidia":
        logger.error(
            "Unsupported AI_PROVIDER=%s. This service is currently configured "
            "for NVIDIA NIM.",
            settings.AI_PROVIDER,
        )
        return _clarification_fallback(
            "The AI booking assistant isn't configured correctly. "
            "Please use the regular booking form instead."
        )

    if not settings.NVIDIA_API_KEY:
        logger.warning(
            "NVIDIA_API_KEY is not configured. AI parsing cannot run."
        )
        return _clarification_fallback(
            "The AI booking assistant isn't configured yet. "
            "Please use the regular booking form instead."
        )

    today = dt.date.today()
    system_prompt = _build_system_prompt(
        today,
        valid_specializations,
    )

    try:
        raw = _parse_with_nvidia(
            natural_language,
            system_prompt,
        )

    except openai.APITimeoutError:
        logger.error(
            "NVIDIA API timed out while parsing appointment request."
        )
        return _clarification_fallback(
            "I'm having trouble processing that right now. "
            "Could you try again in a moment?"
        )

    except openai.AuthenticationError:
        logger.error(
            "NVIDIA API authentication failed. Check NVIDIA_API_KEY."
        )
        return _clarification_fallback(
            "The AI booking assistant isn't configured correctly. "
            "Please use the regular booking form instead."
        )

    except openai.APIError as exc:
        logger.error(
            "NVIDIA API error while parsing appointment request: %s",
            exc,
        )
        return _clarification_fallback(
            "I'm having trouble processing that request right now. "
            "Please try again in a moment."
        )

    except Exception as exc:
        logger.error(
            "Unexpected error calling NVIDIA API: %s",
            exc,
        )
        return _clarification_fallback(
            "I'm having trouble processing that right now. "
            "Could you try again?"
        )

    # Normalize the date before Pydantic validation.
    raw_date = raw.get("preferred_date")
    resolved_date = _resolve_relative_date(
        raw_date,
        today,
    )

    if raw_date and not resolved_date:
        logger.warning(
            "NVIDIA returned an unparsable date: %r",
            raw_date,
        )
        return _clarification_fallback(
            "I couldn't determine the exact appointment date. "
            "Could you give me a specific date?"
        )

    # Normalize the specialization against the actual database list.
    specialization_name = raw.get("specialization_name")

    if specialization_name:
        match = next(
            (
                specialization
                for specialization in valid_specializations
                if specialization.lower() == specialization_name.strip().lower()
            ),
            None,
        )

        specialization_name = match

    try:
        parsed = ParsedAppointmentRequest(
            specialization_name=specialization_name,
            doctor_name=raw.get("doctor_name"),
            preferred_date=resolved_date,
            time_of_day=raw.get("time_of_day"),
            urgency=raw.get("urgency"),
            experience_preference=raw.get("experience_preference"),
            wait_preference=raw.get("wait_preference"),
            appointment_type=raw.get("appointment_type"),
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

    missing = list(raw.get("missing_fields") or [])

    if not parsed.specialization_name and "specialty" not in missing:
        missing.append("specialty")

    if not parsed.preferred_date and "date" not in missing:
        missing.append("date")

    if missing:
        question = raw.get("clarification_question") or (
            f"Could you tell me the {' and '.join(missing)} "
            "you'd like for this appointment?"
        )

        return AIParseResponse(
            status="needs_clarification",
            missing_fields=missing,
            clarification_question=question,
        )

    return AIParseResponse(
        status="complete",
        data=parsed,
    )