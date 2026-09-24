"""
Single source of truth for "is this doctor actually free at this time".

Every part of the app that needs to reason about doctor availability
(the plain slots endpoint, the recommendation engine, and the AI candidate
finder) calls into this module instead of re-implementing the same
interval-overlap logic slightly differently (which is how the original
project ended up with several inconsistent, buggy copies of it).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.doctor_availability import DoctorAvailability
from app.models.doctor_leave import DoctorLeave
from app.models.enums import AppointmentStatus

# Appointment statuses that hold a real claim on the calendar.
ACTIVE_APPOINTMENT_STATUSES = (AppointmentStatus.scheduled, AppointmentStatus.rescheduled)


def intervals_overlap(start_a: dt.datetime, end_a: dt.datetime, start_b: dt.datetime, end_b: dt.datetime) -> bool:
    """True if [start_a, end_a) overlaps [start_b, end_b). Half-open intervals:
    an appointment ending at 10:00 does not conflict with one starting at 10:00."""
    return start_a < end_b and end_a > start_b


def _fits_in_one_window(
    windows: Sequence[Tuple[dt.time, dt.time]], start_time: dt.time, end_time: dt.time
) -> bool:
    """
    The appointment must fit entirely inside a SINGLE availability window.
    A doctor with 09:00-12:00 and 14:00-17:00 must NOT accept 11:30-14:30,
    even though both endpoints individually fall inside *some* window.
    """
    for window_start, window_end in windows:
        if window_start <= start_time and end_time <= window_end:
            return True
    return False


def doctor_leave_overlaps(db: Session, doctor_id: int, start_datetime: dt.datetime, end_datetime: dt.datetime) -> bool:
    """A leave period overlaps the appointment when leave.start < appt.end AND leave.end > appt.start."""
    leave = (
        db.query(DoctorLeave)
        .filter(
            DoctorLeave.doctor_id == doctor_id,
            DoctorLeave.start_datetime < end_datetime,
            DoctorLeave.end_datetime > start_datetime,
        )
        .first()
    )
    return leave is not None


def get_conflicting_appointment(
    db: Session,
    doctor_id: int,
    start_datetime: dt.datetime,
    end_datetime: dt.datetime,
    exclude_appointment_id: Optional[int] = None,
    lock: bool = False,
) -> Optional[Appointment]:
    """
    Any existing active appointment for the doctor whose interval overlaps
    [start_datetime, end_datetime). Overlap is a genuine range check, not just
    an equal-start-time check, so 10:00-10:45 correctly conflicts with 10:30-11:00.
    """
    query = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        Appointment.start_datetime < end_datetime,
        Appointment.end_datetime > start_datetime,
    )
    if exclude_appointment_id is not None:
        query = query.filter(Appointment.id != exclude_appointment_id)
    if lock:
        query = query.with_for_update()
    return query.first()


def fits_within_availability(
    db: Session, doctor_id: int, start_datetime: dt.datetime, end_datetime: dt.datetime
) -> bool:
    """The whole [start, end) span must fit inside one of the doctor's weekly
    availability windows for that day of week."""
    day_of_week = start_datetime.weekday()
    if start_datetime.date() != end_datetime.date():
        # An appointment cannot span midnight into a different weekly window.
        return False

    windows = (
        db.query(DoctorAvailability.start_time, DoctorAvailability.end_time)
        .filter(DoctorAvailability.doctor_id == doctor_id, DoctorAvailability.day_of_week == day_of_week)
        .all()
    )
    if not windows:
        return False

    return _fits_in_one_window(windows, start_datetime.time(), end_datetime.time())


@dataclass
class CandidateSlot:
    start_datetime: dt.datetime
    end_datetime: dt.datetime

    @property
    def time_str(self) -> str:
        return self.start_datetime.strftime("%H:%M")


def generate_available_slots(
    db: Session,
    doctor_id: int,
    target_date: dt.date,
    slot_duration_minutes: Optional[int] = None,
) -> List[CandidateSlot]:
    """
    Generate every open slot for a doctor on a given date: inside a weekly
    availability window, not blocked by leave, and not conflicting with an
    existing active appointment. If slot_duration_minutes is not given, each
    availability window's own slot_duration is used.
    """
    day_of_week = target_date.weekday()
    windows = (
        db.query(DoctorAvailability)
        .filter(DoctorAvailability.doctor_id == doctor_id, DoctorAvailability.day_of_week == day_of_week)
        .all()
    )
    if not windows:
        return []

    day_start = dt.datetime.combine(target_date, dt.time.min)
    day_end = dt.datetime.combine(target_date, dt.time.max)

    leaves = (
        db.query(DoctorLeave)
        .filter(
            DoctorLeave.doctor_id == doctor_id,
            DoctorLeave.start_datetime <= day_end,
            DoctorLeave.end_datetime >= day_start,
        )
        .all()
    )
    existing_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.start_datetime >= day_start,
            Appointment.start_datetime <= day_end,
        )
        .all()
    )

    blocked: List[Tuple[dt.datetime, dt.datetime]] = []
    for leave in leaves:
        clipped_start = max(leave.start_datetime, day_start)
        clipped_end = min(leave.end_datetime, day_end)
        if clipped_start < clipped_end:
            blocked.append((clipped_start, clipped_end))
    for appt in existing_appointments:
        blocked.append((appt.start_datetime, appt.end_datetime))

    slots: List[CandidateSlot] = []
    for window in windows:
        duration = slot_duration_minutes or window.slot_duration
        current = dt.datetime.combine(target_date, window.start_time)
        window_end = dt.datetime.combine(target_date, window.end_time)
        step = dt.timedelta(minutes=duration)
        while current + step <= window_end:
            slot_end = current + step
            is_blocked = any(intervals_overlap(current, slot_end, b_start, b_end) for b_start, b_end in blocked)
            if not is_blocked:
                slots.append(CandidateSlot(start_datetime=current, end_datetime=slot_end))
            current += step

    slots.sort(key=lambda s: s.start_datetime)
    return slots
