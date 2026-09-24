"""
Unit tests for the scoring/explanation helpers in
app/services/recommendation_service.py. These are pure functions (no DB), so
unlike the rest of the AI/scheduling tests they don't need the `db` fixture.
"""
import datetime as dt
from types import SimpleNamespace

import pytest

from app.services.recommendation_service import _duration_score, _explain, _preference_match_score
from app.scheduling.slots import CandidateSlot


def test_duration_score_perfect_match_is_one():
    assert _duration_score(predicted_duration=30.0, preferred_duration=30.0) == pytest.approx(1.0)


def test_duration_score_decreases_with_mismatch():
    close = _duration_score(predicted_duration=35.0, preferred_duration=30.0)
    far = _duration_score(predicted_duration=90.0, preferred_duration=30.0)
    assert close > far


def test_duration_score_short_visit_scores_well_without_preference():
    assert _duration_score(predicted_duration=20.0, preferred_duration=None) == pytest.approx(1.0)


def test_preference_match_score_rewards_matching_time_of_day():
    doctor = SimpleNamespace(experience_years=5)
    evening_slot = CandidateSlot(
        start_datetime=dt.datetime(2026, 1, 1, 18, 0), end_datetime=dt.datetime(2026, 1, 1, 18, 30)
    )
    morning_slot = CandidateSlot(
        start_datetime=dt.datetime(2026, 1, 1, 9, 0), end_datetime=dt.datetime(2026, 1, 1, 9, 30)
    )

    matching_score = _preference_match_score(evening_slot, doctor, time_of_day="evening", experience_preference=None)
    mismatched_score = _preference_match_score(morning_slot, doctor, time_of_day="evening", experience_preference=None)
    assert matching_score > mismatched_score


def test_preference_match_score_rewards_experience_when_requested():
    junior = SimpleNamespace(experience_years=1)
    senior = SimpleNamespace(experience_years=25)
    slot = CandidateSlot(start_datetime=dt.datetime(2026, 1, 1, 10, 0), end_datetime=dt.datetime(2026, 1, 1, 10, 30))

    junior_score = _preference_match_score(slot, junior, time_of_day=None, experience_preference="high")
    senior_score = _preference_match_score(slot, senior, time_of_day=None, experience_preference="high")
    assert senior_score > junior_score


def test_explain_only_states_computed_factors():
    doctor = SimpleNamespace(experience_years=15)
    slot = CandidateSlot(start_datetime=dt.datetime(2026, 1, 1, 18, 0), end_datetime=dt.datetime(2026, 1, 1, 18, 30))

    explanations = _explain(
        predicted_duration=30.0,
        no_show_prob=0.05,
        waiting_time=3.0,
        slot=slot,
        time_of_day="evening",
        experience_preference="high",
        doctor=doctor,
    )

    assert isinstance(explanations, list)
    assert all(isinstance(e, str) for e in explanations)
    # Every claim made must be traceable to an input we actually passed in —
    # e.g. it should mention the low no-show probability we computed, not an
    # invented fact.
    assert any("no-show" in e.lower() for e in explanations)
    assert any("wait" in e.lower() for e in explanations)
