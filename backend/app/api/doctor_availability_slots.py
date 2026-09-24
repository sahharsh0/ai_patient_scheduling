from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional
from app.core.database import get_db
from app.models.doctor import Doctor
from app.models.user import User
from app.scheduling.slots import generate_available_slots

router = APIRouter(prefix="/api/doctor-availability-slots", tags=["doctor-availability-slots"])


class AvailableSlotOut(BaseModel):
    """
    A single bookable slot, carrying its REAL start/end and duration (each
    availability window can have its own slot_duration, 5-120 minutes — see
    app/models/doctor_availability.py) instead of just an "HH:mm" string.
    The client books using start_datetime/end_datetime verbatim rather than
    reconstructing them from the date + time-string, which used to (a)
    hardcode a 30-minute duration regardless of the doctor's configured
    slot length, and (b) risk an off-by-one-day shift: `new Date("YYYY-MM-DD")`
    is parsed as UTC midnight per the JS spec, and calling `.setHours()`
    (which operates in the browser's LOCAL time) on that could silently
    land on the wrong calendar day for negative-UTC-offset time zones.
    start_datetime/end_datetime are naive local datetimes (no timezone
    suffix), consistent with how they're stored everywhere else in this
    app; browsers parse a timezone-less ISO string as local time, which is
    exactly the wall-clock time the doctor's availability was defined in.
    """

    time: str  # "HH:MM", kept for display
    start_datetime: str
    end_datetime: str
    duration_minutes: int


@router.get("", response_model=List[AvailableSlotOut])
def get_doctor_availability_slots(
    doctor_id: int,
    date: str,  # Expected format: YYYY-MM-DD
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    Get available slots for a doctor on a given date. Delegates to
    app.scheduling.slots, the single source of truth for
    availability/leave/overlap logic used across the app.
    """
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    slots = generate_available_slots(db, doctor_id, target_date)
    return [
        AvailableSlotOut(
            time=s.time_str,
            start_datetime=s.start_datetime.isoformat(),
            end_datetime=s.end_datetime.isoformat(),
            duration_minutes=int((s.end_datetime - s.start_datetime).total_seconds() // 60),
        )
        for s in slots
    ]
