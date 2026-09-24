from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_doctor
from app.core.database import get_db
from app.models.doctor import Doctor
from app.models.doctor_leave import DoctorLeave
from app.models.user import User
from app.scheduling.slots import ACTIVE_APPOINTMENT_STATUSES
from app.models.appointment import Appointment
from app.schemas.doctor_leave import DoctorLeaveCreate, DoctorLeaveRead, DoctorLeaveUpdate, DoctorLeaveWriteResponse

router = APIRouter(prefix="/api/doctor-leave", tags=["doctor-leave"])


def _conflicting_appointment_ids(db: Session, doctor_id: int, start_datetime, end_datetime) -> List[int]:
    """Already-scheduled appointments that overlap this leave period — see
    DoctorLeaveWriteResponse for why these are surfaced, not blocked."""
    rows = (
        db.query(Appointment.id)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.start_datetime < end_datetime,
            Appointment.end_datetime > start_datetime,
        )
        .all()
    )
    return [r[0] for r in rows]


@router.get("/{doctor_id}", response_model=List[DoctorLeaveRead])
def get_doctor_leave(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all leave periods for a specific doctor.
    Accessible by any authenticated user (patient, doctor, admin).
    """
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    return db.query(DoctorLeave).filter(DoctorLeave.doctor_id == doctor_id).all()


@router.post("", response_model=DoctorLeaveWriteResponse, status_code=status.HTTP_201_CREATED)
def create_doctor_leave(
    leave_in: DoctorLeaveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),  # Only doctors can manage their own leave
):
    """Create a new leave period for the current doctor."""
    if not current_user.doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    doctor_id = current_user.doctor.id

    leave = DoctorLeave(doctor_id=doctor_id, **leave_in.dict())
    db.add(leave)
    db.commit()
    db.refresh(leave)

    conflicts = _conflicting_appointment_ids(db, doctor_id, leave.start_datetime, leave.end_datetime)
    return DoctorLeaveWriteResponse.model_validate(leave, from_attributes=True).model_copy(
        update={"conflicting_appointment_ids": conflicts}
    )


@router.put("/{leave_id}", response_model=DoctorLeaveWriteResponse)
def update_doctor_leave(
    leave_id: int,
    leave_in: DoctorLeaveUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    """Update an existing leave period for the current doctor."""
    if not current_user.doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    doctor_id = current_user.doctor.id

    leave = db.query(DoctorLeave).filter(DoctorLeave.id == leave_id, DoctorLeave.doctor_id == doctor_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave period not found")

    for field, value in leave_in.dict(exclude_unset=True).items():
        setattr(leave, field, value)

    db.commit()
    db.refresh(leave)

    conflicts = _conflicting_appointment_ids(db, doctor_id, leave.start_datetime, leave.end_datetime)
    return DoctorLeaveWriteResponse.model_validate(leave, from_attributes=True).model_copy(
        update={"conflicting_appointment_ids": conflicts}
    )


@router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doctor_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    """Delete a leave period for the current doctor."""
    if not current_user.doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    doctor_id = current_user.doctor.id

    leave = db.query(DoctorLeave).filter(DoctorLeave.id == leave_id, DoctorLeave.doctor_id == doctor_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave period not found")

    db.delete(leave)
    db.commit()
    return None
