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
    ADMIN = "admin"


class BookingOutcome(StrEnum):
    """Tutor-set result of a past individual lesson (section: activity log). Left
    unset (None on the model) until the tutor records it; the log/UI treat an unset
    past-and-still-scheduled booking as CONDUCTED by default."""

    CONDUCTED = "conducted"
    STUDENT_NO_SHOW = "student_no_show"
    TUTOR_NO_SHOW = "tutor_no_show"


class GroupAttendanceOutcome(StrEnum):
    """Per-student result of a past group occurrence - unlike individual lessons a
    group session can be partially attended, so this is tracked per (occurrence,
    student) rather than on the occurrence itself."""

    CONDUCTED = "conducted"
    STUDENT_NO_SHOW = "student_no_show"


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


class ActivityEventType(StrEnum):
    """Filterable categories in the tutor/student activity log (Статистика page).
    Purely a read-model classification - see app.services.activity_log_service -
    derived from Booking/GroupOccurrence/GroupAttendance/GroupApplication/
    GroupMembership rather than stored directly."""

    LESSON_CONDUCTED = "lesson_conducted"
    LESSON_STUDENT_NO_SHOW = "lesson_student_no_show"
    LESSON_TUTOR_NO_SHOW = "lesson_tutor_no_show"
    LESSON_CANCELLED_BY_STUDENT = "lesson_cancelled_by_student"
    LESSON_CANCELLED_BY_TUTOR = "lesson_cancelled_by_tutor"
    LESSON_RESCHEDULED = "lesson_rescheduled"
    GROUP_LESSON_CONDUCTED = "group_lesson_conducted"
    GROUP_LESSON_STUDENT_NO_SHOW = "group_lesson_student_no_show"
    GROUP_LESSON_CANCELLED = "group_lesson_cancelled"
    GROUP_LESSON_RESCHEDULED = "group_lesson_rescheduled"
    GROUP_APPLICATION_ACCEPTED = "group_application_accepted"
    GROUP_APPLICATION_REJECTED = "group_application_rejected"
    GROUP_MEMBERSHIP_LEFT = "group_membership_left"
    GROUP_MEMBERSHIP_REMOVED = "group_membership_removed"
