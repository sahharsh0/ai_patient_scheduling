from sqlalchemy import ForeignKey, Numeric, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    specialization_id: Mapped[int] = mapped_column(
        ForeignKey("specializations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    experience_years: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    consultation_fee: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0)

    user: Mapped["User"] = relationship(back_populates="doctor")
    specialization: Mapped["Specialization"] = relationship(back_populates="doctors")
    availability: Mapped[list["DoctorAvailability"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    leaves: Mapped[list["DoctorLeave"]] = relationship(back_populates="doctor", cascade="all, delete-orphan")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="doctor")
