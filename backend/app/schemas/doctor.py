from typing import Optional

from pydantic import BaseModel, ConfigDict


class SpecializationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None


class DoctorRead(BaseModel):
    """
    Public-facing doctor profile used by doctor listing, booking, and the
    recommendation system. Only fields that actually exist on the Doctor/User
    models are included — nothing here is invented for the UI.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    specialization: Optional[SpecializationRead] = None
    experience_years: int
    consultation_fee: float
    rating: float
    bio: Optional[str] = None

    @classmethod
    def from_orm_doctor(cls, doctor) -> "DoctorRead":
        return cls(
            id=doctor.id,
            name=doctor.user.name if doctor.user else "Unknown",
            specialization=SpecializationRead.model_validate(doctor.specialization) if doctor.specialization else None,
            experience_years=doctor.experience_years,
            consultation_fee=float(doctor.consultation_fee or 0),
            rating=float(doctor.rating or 0),
            bio=doctor.bio,
        )
