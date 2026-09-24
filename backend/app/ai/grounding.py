"""
Database grounding for the AI booking flow.

The LLM only ever deals in human concepts (a specialization *name*, a
doctor's *name*, a calendar date). Turning those into actual primary keys is
plain SQL, done here — the LLM never generates a specialization_id or
doctor_id, and never sees one it's expected to reuse.
"""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.doctor import Doctor
from app.models.specialization import Specialization
from app.models.user import User


def list_specialization_names(db: Session) -> List[str]:
    """The exact, current list of valid specialization names, injected into the
    LLM prompt so it can only choose a name that really exists (or return null)."""
    rows = db.query(Specialization.name).order_by(Specialization.name).all()
    return [r[0] for r in rows]


def resolve_specialization(db: Session, specialization_name: Optional[str]) -> Optional[Specialization]:
    """Case-insensitive exact match against real specialization rows. Returns
    None (not a guess) if the name doesn't match anything — the caller is
    responsible for asking a clarifying question in that case."""
    if not specialization_name:
        return None
    return (
        db.query(Specialization)
        .filter(func.lower(Specialization.name) == specialization_name.strip().lower())
        .first()
    )


def resolve_doctor_by_name(db: Session, doctor_name: Optional[str], specialization_id: Optional[int] = None) -> Optional[Doctor]:
    """Best-effort resolution of a doctor mentioned by name. Matches against
    the User.name of doctor accounts. Returns None if nothing matches — the
    caller should not silently fall back to an arbitrary doctor."""
    if not doctor_name:
        return None
    query = db.query(Doctor).join(User, Doctor.user_id == User.id).filter(func.lower(User.name).like(f"%{doctor_name.strip().lower()}%"))
    if specialization_id is not None:
        query = query.filter(Doctor.specialization_id == specialization_id)
    return query.first()


def find_candidate_doctors(db: Session, specialization_id: Optional[int], doctor_id: Optional[int] = None) -> List[Doctor]:
    """All doctors matching the resolved specialization (or a single named
    doctor), for candidate-slot generation."""
    query = db.query(Doctor)
    if doctor_id is not None:
        query = query.filter(Doctor.id == doctor_id)
    elif specialization_id is not None:
        query = query.filter(Doctor.specialization_id == specialization_id)
    else:
        return []
    return query.all()


def resolve_time_of_day_window(time_of_day: Optional[str]) -> tuple[dt.time, dt.time]:
    """Maps a human time-of-day phrase to a concrete clock-time window used to
    filter/prioritize candidate slots. Falls back to the full day."""
    mapping = {
        "morning": (dt.time(6, 0), dt.time(12, 0)),
        "afternoon": (dt.time(12, 0), dt.time(17, 0)),
        "evening": (dt.time(17, 0), dt.time(21, 0)),
    }
    if time_of_day and time_of_day.lower() in mapping:
        return mapping[time_of_day.lower()]
    return (dt.time(0, 0), dt.time(23, 59))
