"""
Tests for app/ai/service.py: parse_appointment_request(natural_language,
valid_specializations). The Anthropic client is mocked out entirely — these
tests verify OUR handling of its responses (tool-use extraction, Pydantic
validation, clarification fallbacks), not Claude itself.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import app.ai.service as ai_service


VALID_SPECIALIZATIONS = ["Cardiology", "Dermatology", "Orthopedics", "Neurology"]


def _tool_use_message(tool_input: dict):
    """Build a fake Anthropic Message with a single tool_use content block,
    matching what app/ai/service.py expects to find in message.content."""
    block = SimpleNamespace(type="tool_use", input=tool_input)
    return SimpleNamespace(content=[block])


def test_missing_api_key_returns_clarification_not_crash(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ANTHROPIC_API_KEY", "")
    result = ai_service.parse_appointment_request("I need a cardiologist tomorrow", VALID_SPECIALIZATIONS)
    assert result.status == "needs_clarification"
    assert result.clarification_question is not None


def test_complete_request_is_parsed_into_human_concepts(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ANTHROPIC_API_KEY", "test-key")

    fake_message = _tool_use_message({
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
    mock_client.messages.create.return_value = fake_message

    with patch.object(ai_service.anthropic, "Anthropic", return_value=mock_client):
        result = ai_service.parse_appointment_request(
            "I need a cardiologist tomorrow evening, someone experienced, I don't want to wait long",
            VALID_SPECIALIZATIONS,
        )

    assert result.status == "complete"
    assert result.data is not None
    # Human concepts only — never a database ID.
    assert result.data.specialization_name == "Cardiology"
    assert result.data.preferred_date is not None
    assert result.data.time_of_day == "evening"
    assert result.data.experience_preference == "high"
    assert result.data.wait_preference == "low"
    assert not hasattr(result.data, "doctor_id")
    assert not hasattr(result.data, "specialization_id")


def test_specialization_outside_valid_list_is_dropped_not_invented(monkeypatch):
    """If the model names a specialization that isn't in the real list we
    gave it, we must not silently accept it — the missing-field logic should
    kick in instead of booking against a nonexistent specialty."""
    monkeypatch.setattr(ai_service.settings, "ANTHROPIC_API_KEY", "test-key")

    fake_message = _tool_use_message({
        "specialization_name": "Podiatry",  # not in VALID_SPECIALIZATIONS
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
    mock_client.messages.create.return_value = fake_message

    with patch.object(ai_service.anthropic, "Anthropic", return_value=mock_client):
        result = ai_service.parse_appointment_request("I need a podiatrist tomorrow", VALID_SPECIALIZATIONS)

    assert result.status == "needs_clarification"
    assert "specialty" in (result.missing_fields or [])


def test_missing_date_triggers_clarification(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ANTHROPIC_API_KEY", "test-key")

    fake_message = _tool_use_message({
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
    mock_client.messages.create.return_value = fake_message

    with patch.object(ai_service.anthropic, "Anthropic", return_value=mock_client):
        result = ai_service.parse_appointment_request("I need a cardiologist", VALID_SPECIALIZATIONS)

    assert result.status == "needs_clarification"
    assert "date" in (result.missing_fields or [])


def test_api_error_returns_clarification_not_crash(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ANTHROPIC_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("network is down")

    with patch.object(ai_service.anthropic, "Anthropic", return_value=mock_client):
        result = ai_service.parse_appointment_request("I need a cardiologist tomorrow", VALID_SPECIALIZATIONS)

    assert result.status == "needs_clarification"
    assert result.clarification_question is not None


def test_no_tool_use_block_returns_clarification_not_crash(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ANTHROPIC_API_KEY", "test-key")
    fake_message = SimpleNamespace(content=[SimpleNamespace(type="text", text="I'm not sure how to help.")])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_message

    with patch.object(ai_service.anthropic, "Anthropic", return_value=mock_client):
        result = ai_service.parse_appointment_request("???", VALID_SPECIALIZATIONS)

    assert result.status == "needs_clarification"
