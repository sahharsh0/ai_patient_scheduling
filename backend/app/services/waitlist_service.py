"""
Waitlist (Phase 14). A patient can express interest in a specialization on a
preferred date when no slot currently fits; when a matching cancellation
happens, we look up matching waitlist entries and notify those patients.
"""
import datetime as dt
from typing import List

from sqlalchemy.orm import Session

from app.models.enums import WaitlistStatus
from app.models.waitlist import Waitlist
from app.services.notification_service import notify_waitlist_slot_available


def create_waitlist_entry(db: Session, patient_id: int, data) -> Waitlist:
    entry = Waitlist(
        patient_id=patient_id,
        specialization_id=data.specialization_id,
        preferred_date=data.preferred_date,
        earliest_time=data.earliest_time,
        latest_time=data.latest_time,
        priority=data.priority,
        status=WaitlistStatus.waiting,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_patient_waitlist(db: Session, patient_id: int) -> List[Waitlist]:
    return (
        db.query(Waitlist)
        .filter(Waitlist.patient_id == patient_id)
        .order_by(Waitlist.created_at.desc())
        .all()
    )


def find_matching_waitlist_entries(db: Session, specialization_id: int, freed_start: dt.datetime) -> List[Waitlist]:
    """Waiting entries whose specialization matches and whose date/time window
    covers the newly freed slot."""
    freed_date = freed_start.date()
    freed_time = freed_start.time()
    candidates = (
        db.query(Waitlist)
        .filter(
            Waitlist.specialization_id == specialization_id,
            Waitlist.preferred_date == freed_date,
            Waitlist.status == WaitlistStatus.waiting,
        )
        .order_by(Waitlist.priority.desc(), Waitlist.created_at.asc())
        .all()
    )
    matches = []
    for entry in candidates:
        if entry.earliest_time and freed_time < entry.earliest_time:
            continue
        if entry.latest_time and freed_time > entry.latest_time:
            continue
        matches.append(entry)
    return matches


def notify_matching_waitlist_entries(db: Session, specialization_id: int, freed_start: dt.datetime) -> int:
    """Called after a cancellation frees up a slot. Marks matching entries as
    'offered' and sends a notification. Returns the number notified."""
    matches = find_matching_waitlist_entries(db, specialization_id, freed_start)
    for entry in matches:
        entry.status = WaitlistStatus.offered
        notify_waitlist_slot_available(db, entry)
    if matches:
        db.commit()
    return len(matches)
