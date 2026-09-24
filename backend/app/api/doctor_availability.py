from app.models.user import User
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_current_user, require_doctor, require_admin
from app.core.database import get_db
from app.models.doctor import Doctor
from app.models.doctor_availability import DoctorAvailability
from app.schemas.doctor_availability import DoctorAvailabilityCreate, DoctorAvailabilityUpdate, DoctorAvailabilityRead

router = APIRouter(prefix="/api/doctor-availability", tags=["doctor-availability"])


@router.get("/{doctor_id}", response_model=List[DoctorAvailabilityRead])
def get_doctor_availability(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all availability slots for a specific doctor.
    Accessible by any authenticated user (patient, doctor, admin).
    """
    # Verify doctor exists
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    availability = db.query(DoctorAvailability).filter(
        DoctorAvailability.doctor_id == doctor_id
    ).all()
    return availability


@router.post("", response_model=DoctorAvailabilityRead, status_code=status.HTTP_201_CREATED)
def create_doctor_availability(
    availability_in: DoctorAvailabilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),  # Only doctors can manage their own availability
):
    """
    Create a new availability slot for the current doctor.
    """
    # Verify the current user is a doctor and get their doctor profile
    if not current_user.doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    doctor_id = current_user.doctor.id
    
    # Create new availability slot
    availability = DoctorAvailability(
        doctor_id=doctor_id,
        **availability_in.dict()
    )
    db.add(availability)
    db.commit()
    db.refresh(availability)
    return availability


@router.put("/{availability_id}", response_model=DoctorAvailabilityRead)
def update_doctor_availability(
    availability_id: int,
    availability_in: DoctorAvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    """
    Update an existing availability slot for the current doctor.
    """
    # Verify the current user is a doctor and get their doctor profile
    if not current_user.doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    doctor_id = current_user.doctor.id
    
    # Get the availability slot
    availability = db.query(DoctorAvailability).filter(
        DoctorAvailability.id == availability_id,
        DoctorAvailability.doctor_id == doctor_id
    ).first()
    
    if not availability:
        raise HTTPException(status_code=404, detail="Availability slot not found")
    
    # Update the availability slot
    for field, value in availability_in.dict(exclude_unset=True).items():
        setattr(availability, field, value)
    
    db.commit()
    db.refresh(availability)
    return availability


@router.delete("/{availability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doctor_availability(
    availability_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    """
    Delete an availability slot for the current doctor.
    """
    # Verify the current user is a doctor and get their doctor profile
    if not current_user.doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    
    doctor_id = current_user.doctor.id
    
    # Get the availability slot
    availability = db.query(DoctorAvailability).filter(
        DoctorAvailability.id == availability_id,
        DoctorAvailability.doctor_id == doctor_id
    ).first()
    
    if not availability:
        raise HTTPException(status_code=404, detail="Availability slot not found")
    
    db.delete(availability)
    db.commit()
    return None
