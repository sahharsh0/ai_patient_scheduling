import datetime as dt

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PredictionLog(Base):
    """
    Records every ML/AI prediction made by the system (duration, no-show,
    waiting time, LLM parses) for debugging, auditing, and future model
    evaluation. Not linked with a hard FK to appointments since predictions
    can happen before an appointment exists (e.g. during ranking).
    """

    __tablename__ = "prediction_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    input_features: Mapped[dict] = mapped_column(JSON, nullable=False)
    prediction: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
