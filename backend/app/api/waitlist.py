from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_patient
from app.core.database import get_db
from app.models.user import User
from app.schemas.waitlist import WaitlistCreate, WaitlistRead
from app.services.waitlist_service import create_waitlist_entry, get_patient_waitlist

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])


@router.post("", response_model=WaitlistRead, status_code=status.HTTP_201_CREATED)
def join_waitlist(
    payload: WaitlistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    if not current_user.patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return create_waitlist_entry(db, patient_id=current_user.patient.id, data=payload)


@router.get("", response_model=List[WaitlistRead])
def list_my_waitlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    if not current_user.patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return get_patient_waitlist(db, patient_id=current_user.patient.id)
