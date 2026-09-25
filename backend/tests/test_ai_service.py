"""
Tests for app/ai/service.py.

The NVIDIA/OpenAI-compatible client is mocked out entirely.
These tests verify our handling of AI responses, tool-call extraction,
validation, specialization matching, and clarification fallbacks.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app.ai.service as ai_service


VALID_SPECIALIZATIONS = [
    "Cardiology",
    "Dermatology",
    "Orthopedics",
    "Neurology",
]

def _tool_call_response(tool_input: dict):
    """Build a fake OpenAI response containing one tool call."""

    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            name="record_appointment_request",
            arguments=__import__("json").dumps(tool_input),
        )
    )

    message = SimpleNamespace(
        tool_calls=[tool_call]
    )

    choice = SimpleNamespace(
        message=message
    )

    return SimpleNamespace(
        choices=[choice]
    )


def test_missing_api_key_returns_clarification_not_crash(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "NVIDIA_API_KEY", "")

    result = ai_service.parse_appointment_request(
        "I need a cardiologist tomorrow",
        VALID_SPECIALIZATIONS,
    )

    assert result.status == "needs_clarification"
    assert result.clarification_question is not None


def test_complete_request_is_parsed_into_human_concepts(monkeypatch):
    monkeypatch.setattr(
        ai_service.settings,
        "NVIDIA_API_KEY",
        "test-key",
    )

    fake_response = _tool_call_response({
        "specialization_name": "Cardiology",
        "doctor_name": None,
        "preferred_date": "2026-09-21",
        "time_of_day": "evening",
        "urgency": None,
        "experience_preference": "high",
        "wait_preference": "low",
        "appointment_type": None,
        "missing_fields": [],
        "clarification_question": None,
    })

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_response

    with patch.object(
        ai_service,
        "OpenAI",
        return_value=mock_client,
    ):
        result = ai_service.parse_appointment_request(
            "I need a cardiologist tomorrow evening, "
            "someone experienced, I don't want to wait long",
            VALID_SPECIALIZATIONS,
        )

    assert result.status == "complete"
    assert result.data is not None

    # Human concepts only — never database IDs.
    assert result.data.specialization_name == "Cardiology"
    assert result.data.preferred_date is not None
    assert result.data.time_of_day == "evening"
    assert result.data.experience_preference == "high"
    assert result.data.wait_preference == "low"

    assert not hasattr(result.data, "doctor_id")
    assert not hasattr(result.data, "specialization_id")


def test_specialization_outside_valid_list_is_dropped_not_invented(
    monkeypatch,
):
    """
    If the model names a specialization that isn't in the real list
    we supplied, we must not silently accept it.
    """

    monkeypatch.setattr(
        ai_service.settings,
        "NVIDIA_API_KEY",
        "test-key",
    )

    fake_response = _tool_call_response({
        "specialization_name": "Podiatry",
        "doctor_name": None,
        "preferred_date": "2026-09-21",
        "time_of_day": None,
        "urgency": None,
        "experience_preference": None,
        "wait_preference": None,
        "appointment_type": None,
        "missing_fields": [],
        "clarification_question": None,
    })

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_response

    with patch.object(
        ai_service,
        "OpenAI",
        return_value=mock_client,
    ):
        result = ai_service.parse_appointment_request(
            "I need a podiatrist tomorrow",
            VALID_SPECIALIZATIONS,
        )

    assert result.status == "needs_clarification"
    assert "specialty" in (result.missing_fields or [])


def test_missing_date_triggers_clarification(monkeypatch):
    monkeypatch.setattr(
        ai_service.settings,
        "NVIDIA_API_KEY",
        "test-key",
    )

    fake_response = _tool_call_response({
        "specialization_name": "Cardiology",
        "doctor_name": None,
        "preferred_date": None,
        "time_of_day": None,
        "urgency": None,
        "experience_preference": None,
        "wait_preference": None,
        "appointment_type": None,
        "missing_fields": [],
        "clarification_question": None,
    })

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_response

    with patch.object(
        ai_service,
        "OpenAI",
        return_value=mock_client,
    ):
        result = ai_service.parse_appointment_request(
            "I need a cardiologist",
            VALID_SPECIALIZATIONS,
        )

    assert result.status == "needs_clarification"
    assert "date" in (result.missing_fields or [])


def test_api_error_returns_clarification_not_crash(monkeypatch):
    monkeypatch.setattr(
        ai_service.settings,
        "NVIDIA_API_KEY",
        "test-key",
    )

    mock_client = MagicMock()

    mock_client.chat.completions.create.side_effect = RuntimeError(
        "network is down"
    )

    with patch.object(
        ai_service,
        "OpenAI",
        return_value=mock_client,
    ):
        result = ai_service.parse_appointment_request(
            "I need a cardiologist tomorrow",
            VALID_SPECIALIZATIONS,
        )

    assert result.status == "needs_clarification"
    assert result.clarification_question is not None


def test_no_tool_call_returns_clarification_not_crash(monkeypatch):
    monkeypatch.setattr(
        ai_service.settings,
        "NVIDIA_API_KEY",
        "test-key",
    )

    fake_message = SimpleNamespace(
        tool_calls=None
    )

    fake_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=fake_message
            )
        ]
    )

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = fake_response

    with patch.object(
        ai_service,
        "OpenAI",
        return_value=mock_client,
    ):
        result = ai_service.parse_appointment_request(
            "???",
            VALID_SPECIALIZATIONS,
        )

    assert result.status == "needs_clarification"