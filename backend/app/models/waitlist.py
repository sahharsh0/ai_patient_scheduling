import datetime as dt

from sqlalchemy import Date, DateTime, Enum, ForeignKey, SmallInteger, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import WaitlistStatus


class Waitlist(Base):
    __tablename__ = "waitlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    specialization_id: Mapped[int] = mapped_column(ForeignKey("specializations.id"), nullable=False)
    preferred_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    earliest_time: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    latest_time: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    status: Mapped[WaitlistStatus] = mapped_column(
        Enum(WaitlistStatus), nullable=False, default=WaitlistStatus.waiting, index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    patient: Mapped["Patient"] = relationship(back_populates="waitlist_entries")
