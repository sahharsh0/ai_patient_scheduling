from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus, BookingSource
from app.models.patient import Patient
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminStats(BaseModel):
    total_patients: int
    total_doctors: int
    total_appointments: int
    scheduled_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    no_show_appointments: int
    ai_booked_appointments: int


@router.get("/stats", response_model=AdminStats)
def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Real statistics computed from the database — not fabricated. Each count
    below is a straightforward COUNT() query against the actual tables.
    """
    def count_by_status(status: AppointmentStatus) -> int:
        return db.query(func.count(Appointment.id)).filter(Appointment.status == status).scalar() or 0

    return AdminStats(
        total_patients=db.query(func.count(Patient.id)).scalar() or 0,
        total_doctors=db.query(func.count(Doctor.id)).scalar() or 0,
        total_appointments=db.query(func.count(Appointment.id)).scalar() or 0,
        scheduled_appointments=count_by_status(AppointmentStatus.scheduled),
        completed_appointments=count_by_status(AppointmentStatus.completed),
        cancelled_appointments=count_by_status(AppointmentStatus.cancelled),
        no_show_appointments=count_by_status(AppointmentStatus.no_show),
        ai_booked_appointments=(
            db.query(func.count(Appointment.id)).filter(Appointment.booking_source == BookingSource.ai).scalar() or 0
        ),
    )
