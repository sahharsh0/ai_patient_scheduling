from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_patient
from app.core.database import get_db
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentUpdate
from app.services.appointment_service import (
    cancel_appointment,
    create_appointment,
    get_appointment,
    get_appointments,
    to_appointment_read,
    update_appointment,
)

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.get("/me", response_model=List[AppointmentRead])
def list_my_appointments(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The identity-safe way for a patient or doctor to fetch their own
    appointments: the patient/doctor record is derived from the authenticated
    user, never from a client-supplied id, so nobody can enumerate another
    person's schedule by changing a query parameter.
    """
    appointments = get_appointments(db=db, skip=skip, limit=limit, status=status, current_user=current_user)
    return [to_appointment_read(a) for a in appointments]


@router.get("", response_model=List[AppointmentRead])
def list_appointments(
    skip: int = 0,
    limit: int = 100,
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List appointments. Patients/doctors are always scoped to their own
    records regardless of the patient_id/doctor_id query params (those are
    only honored for admins) — see app/services/appointment_service.py.
    """
    appointments = get_appointments(
        db=db,
        skip=skip,
        limit=limit,
        patient_id=patient_id,
        doctor_id=doctor_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        current_user=current_user,
    )
    return [to_appointment_read(a) for a in appointments]


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def book_appointment(
    appointment_in: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),  # Only patients can book appointments
):
    """
    Book a new appointment. The scheduling engine checks doctor availability,
    leave, and overlap conflicts inside a transaction (see appointment_service).
    """
    if not current_user.patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    # The patient_id is ALWAYS derived from the authenticated user, never
    # trusted from the request body, so a patient cannot book on someone
    # else's behalf by editing the payload.
    appointment_in.patient_id = current_user.patient.id

    appointment = create_appointment(db=db, appointment_in=appointment_in)
    return to_appointment_read(appointment)


@router.get("/{appointment_id}", response_model=AppointmentRead)
def get_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = get_appointment(db=db, appointment_id=appointment_id, current_user=current_user)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return to_appointment_read(appointment)


@router.put("/{appointment_id}", response_model=AppointmentRead)
def reschedule_appointment(
    appointment_id: int,
    appointment_in: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),  # Only patients can reschedule their appointments
):
    appointment = update_appointment(
        db=db, appointment_id=appointment_id, appointment_in=appointment_in, current_user=current_user
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return to_appointment_read(appointment)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),  # Only patients can cancel their appointments
):
    success = cancel_appointment(db=db, appointment_id=appointment_id, current_user=current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return None
