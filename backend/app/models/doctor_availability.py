from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DoctorAvailability(Base):
    """Recurring weekly working hours for a doctor, e.g. Mon 09:00-17:00 in 30-min slots."""

    __tablename__ = "doctor_availability"
    __table_args__ = (
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_doctor_availability_day_of_week"),
        CheckConstraint("end_time > start_time", name="ck_doctor_availability_end_after_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0=Monday ... 6=Sunday
    start_time = mapped_column(Time, nullable=False)
    end_time = mapped_column(Time, nullable=False)
    slot_duration: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=30)  # minutes

    doctor: Mapped["Doctor"] = relationship(back_populates="availability")
