from enum import StrEnum


class UserRole(StrEnum):
    TUTOR = "tutor"
    STUDENT = "student"
    ADMIN = "admin"


class AuthProvider(StrEnum):
    PASSWORD = "password"
    VK = "vk"


class LessonFormat(StrEnum):
    INDIVIDUAL = "individual"
    GROUP = "group"


class BookingStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED_BY_STUDENT = "cancelled_by_student"
    CANCELLED_BY_TUTOR = "cancelled_by_tutor"
    RESCHEDULED = "rescheduled"
    COMPLETED = "completed"


class BookedBy(StrEnum):
    TUTOR = "tutor"
    STUDENT = "student"


class GroupApplicationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class GroupMembershipStatus(StrEnum):
    ACTIVE = "active"
    LEFT = "left"


class GroupOccurrenceStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
    COMPLETED = "completed"


class HomeworkContentType(StrEnum):
    LINK = "link"
    FILE = "file"


class HomeworkSubmissionMode(StrEnum):
    FILE_UPLOAD = "file_upload"
    MARK_DONE = "mark_done"


class HomeworkSubmissionStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    DONE = "done"


class ChatThreadType(StrEnum):
    INDIVIDUAL = "individual"
    GROUP = "group"


class NotificationChannel(StrEnum):
    TELEGRAM = "telegram"
    EMAIL = "email"


class NotificationEvent(StrEnum):
    NEW_BOOKING = "new_booking"
    UPCOMING_REMINDER = "upcoming_reminder"
    SCHEDULE_CHANGE = "schedule_change"
    GROUP_APPLICATION = "group_application"
    GROUP_WITHDRAWAL = "group_withdrawal"
    NEW_MESSAGE = "new_message"
    OTHER = "other"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
