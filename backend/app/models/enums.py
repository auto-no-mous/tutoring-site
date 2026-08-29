from enum import StrEnum


class UserRole(StrEnum):
    TUTOR = "tutor"
    STUDENT = "student"
    ADMIN = "admin"


class AuthProvider(StrEnum):
    """Способы входа. PASSWORD - почта + пароль, остальные - внешние провайдеры,
    у которых есть строка в user_identities (см. app.services.oauth_providers)."""

    PASSWORD = "password"
    VK = "vk"
    YANDEX = "yandex"


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


class NotificationChannelPref(StrEnum):
    """Как пользователь хочет получать уведомления и напоминания о занятиях
    (Настройки -> "Напоминания и уведомления"). Заменила прежний флаг
    email_notifications_enabled: каналов стало два, и булева галочка их уже не
    описывала."""

    OFF = "off"
    EMAIL = "email"
    TELEGRAM = "telegram"
    BOTH = "both"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class SystemNotificationEvent(StrEnum):
    """In-app "Системные уведомления" thread events - see
    app.services.system_notification_service. Distinct from NotificationEvent (email/
    Telegram dispatch categories, section 2.7): those are coarser (e.g. one
    SCHEDULE_CHANGE covers every cancel/reschedule direction) while admin-editable
    in-app templates need one entry per actor+action so the wording can differ
    ("вы отменили" vs "ученик отменил")."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    WELCOME = "welcome"
    BOOKING_CANCELLED_BY_STUDENT = "booking_cancelled_by_student"
    BOOKING_RESCHEDULED_BY_STUDENT = "booking_rescheduled_by_student"
    GROUP_APPLICATION_RECEIVED = "group_application_received"
    GROUP_MEMBER_LEFT = "group_member_left"
    GROUP_LESSON_NO_SHOW_BY_STUDENT = "group_lesson_no_show_by_student"
    BOOKING_CANCELLED_BY_TUTOR = "booking_cancelled_by_tutor"
    BOOKING_RESCHEDULED_BY_TUTOR = "booking_rescheduled_by_tutor"
    GROUP_SCHEDULE_CHANGED = "group_schedule_changed"
    GROUP_APPLICATION_ACCEPTED = "group_application_accepted"
    GROUP_APPLICATION_REJECTED = "group_application_rejected"
    HOMEWORK_ASSIGNED = "homework_assigned"
    UPCOMING_LESSON_REMINDER = "upcoming_lesson_reminder"
    PASSWORD_CHANGED_BY_ADMIN = "password_changed_by_admin"


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


class EmailDirection(StrEnum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class EmailKind(StrEnum):
    """Что за письмо - для фильтров и статистики в админке."""

    VERIFICATION = "verification"
    PASSWORD_RESET = "password_reset"
    ADMIN = "admin"
    # Уведомления по событиям сайта: запись на занятие, напоминания.
    NOTIFICATION = "notification"
    INBOUND = "inbound"
    OTHER = "other"


class EmailStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    RECEIVED = "received"
