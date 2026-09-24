import enum


class UserRole(str, enum.Enum):
    patient = "patient"
    doctor = "doctor"
    admin = "admin"


class AppointmentStatus(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"
    rescheduled = "rescheduled"


class BookingSource(str, enum.Enum):
    normal = "normal"
    ai = "ai"


class AppointmentType(str, enum.Enum):
    consultation = "consultation"
    follow_up = "follow_up"
    check_up = "check_up"
    procedure = "procedure"


class WaitlistStatus(str, enum.Enum):
    waiting = "waiting"
    offered = "offered"
    booked = "booked"
    expired = "expired"
    cancelled = "cancelled"


class NotificationType(str, enum.Enum):
    booking_confirmation = "booking_confirmation"
    cancellation = "cancellation"
    reschedule = "reschedule"
    reminder = "reminder"
    waitlist_availability = "waitlist_availability"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
