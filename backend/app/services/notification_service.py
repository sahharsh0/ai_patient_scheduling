"""
In-app notifications (Phase 15). Stored in MySQL, no email/SMS.

Every write here is best-effort: a notification failure must never break the
appointment action that triggered it, so callers should treat this the way
`create_notification` treats its own errors — log and continue.
"""
import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.models.enums import NotificationStatus, NotificationType
from app.models.notification import Notification

logger = logging.getLogger(__name__)


def create_notification(
    db: Session,
    user_id: int,
    notification_type: NotificationType,
    message: str,
    appointment_id: int | None = None,
) -> Notification | None:
    try:
        notification = Notification(
            user_id=user_id,
            appointment_id=appointment_id,
            type=notification_type,
            message=message,
            status=NotificationStatus.sent,
            sent_at=dt.datetime.utcnow(),
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification
    except Exception:
        logger.exception("Failed to create notification (user_id=%s, type=%s)", user_id, notification_type)
        db.rollback()
        return None


def notify_appointment_booked(db: Session, appointment) -> None:
    doctor_name = appointment.doctor.user.name if appointment.doctor and appointment.doctor.user else "your doctor"
    create_notification(
        db,
        user_id=appointment.patient.user_id,
        notification_type=NotificationType.booking_confirmation,
        message=f"Your appointment with {doctor_name} on {appointment.start_datetime.strftime('%Y-%m-%d %H:%M')} is confirmed.",
        appointment_id=appointment.id,
    )
    if appointment.doctor and appointment.doctor.user:
        patient_name = appointment.patient.user.name if appointment.patient and appointment.patient.user else "A patient"
        create_notification(
            db,
            user_id=appointment.doctor.user_id,
            notification_type=NotificationType.booking_confirmation,
            message=f"New appointment booked with {patient_name} on {appointment.start_datetime.strftime('%Y-%m-%d %H:%M')}.",
            appointment_id=appointment.id,
        )


def notify_appointment_cancelled(db: Session, appointment) -> None:
    doctor_name = appointment.doctor.user.name if appointment.doctor and appointment.doctor.user else "your doctor"
    create_notification(
        db,
        user_id=appointment.patient.user_id,
        notification_type=NotificationType.cancellation,
        message=f"Your appointment with {doctor_name} on {appointment.start_datetime.strftime('%Y-%m-%d %H:%M')} was cancelled.",
        appointment_id=appointment.id,
    )
    if appointment.doctor and appointment.doctor.user:
        create_notification(
            db,
            user_id=appointment.doctor.user_id,
            notification_type=NotificationType.cancellation,
            message=f"Appointment on {appointment.start_datetime.strftime('%Y-%m-%d %H:%M')} was cancelled by the patient.",
            appointment_id=appointment.id,
        )


def notify_appointment_rescheduled(db: Session, appointment) -> None:
    doctor_name = appointment.doctor.user.name if appointment.doctor and appointment.doctor.user else "your doctor"
    create_notification(
        db,
        user_id=appointment.patient.user_id,
        notification_type=NotificationType.reschedule,
        message=f"Your appointment with {doctor_name} was rescheduled to {appointment.start_datetime.strftime('%Y-%m-%d %H:%M')}.",
        appointment_id=appointment.id,
    )


def notify_waitlist_slot_available(db: Session, waitlist_entry) -> None:
    create_notification(
        db,
        user_id=waitlist_entry.patient.user_id,
        notification_type=NotificationType.waitlist_availability,
        message="A matching appointment slot just became available for your waitlist request.",
    )
