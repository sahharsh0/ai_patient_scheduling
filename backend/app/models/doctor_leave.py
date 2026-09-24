import datetime as dt

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DoctorLeave(Base):
    __tablename__ = "doctor_leaves"
    __table_args__ = (
        CheckConstraint("end_datetime > start_datetime", name="ck_doctor_leave_end_after_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    start_datetime: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    end_datetime: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    doctor: Mapped["Doctor"] = relationship(back_populates="leaves")
