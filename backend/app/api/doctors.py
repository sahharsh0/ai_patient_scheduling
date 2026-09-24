from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user_optional, require_doctor
from app.core.database import get_db
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.doctor import DoctorRead

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


@router.get("/me", response_model=DoctorRead)
def get_my_doctor_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_doctor),
):
    """
    The identity-safe way for a logged-in doctor to find their OWN doctor_id
    (distinct from users.id) — needed by the frontend to call
    /api/doctor-availability/{doctor_id} etc. without guessing an ID.
    """
    if not current_user.doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return DoctorRead.from_orm_doctor(current_user.doctor)


@router.get("", response_model=List[DoctorRead])
def get_doctors(
    specialization_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    List all doctors with their specialization. Public: browsing doctors
    does not require authentication, matching how a real booking site works.
    """
    query = db.query(Doctor).options(joinedload(Doctor.user), joinedload(Doctor.specialization))
    if specialization_id is not None:
        query = query.filter(Doctor.specialization_id == specialization_id)
    doctors = query.all()
    return [DoctorRead.from_orm_doctor(d) for d in doctors]


@router.get("/{doctor_id}", response_model=DoctorRead)
def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return DoctorRead.from_orm_doctor(doctor)
