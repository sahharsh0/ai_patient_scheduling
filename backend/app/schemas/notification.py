import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationStatus, NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_id: Optional[int] = None
    type: NotificationType
    message: str
    status: NotificationStatus
    sent_at: Optional[dt.datetime] = None
