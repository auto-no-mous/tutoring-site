import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import UTCDateTime


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    display_name: str
    first_name: str
    last_name: str
    patronymic: str | None
    grade: int | None
    role: str
    email_verified: bool
    is_active: bool
    timezone: str
    telegram_chat_id: str | None
    email_notifications_enabled: bool
    reminder_lead_minutes: int
    created_at: UTCDateTime


class UserSettingsUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    patronymic: str | None = Field(default=None, max_length=255)
    # School grade (класс); only meaningful for students.
    grade: int | None = Field(default=None, ge=1, le=11)
    # Changing email re-requires verification - see auth_service.update_user_settings.
    email: EmailStr | None = None
    # Student's local timezone override (section 6); meaningless for tutors, whose
    # cabinet always shows MSK regardless.
    timezone: str | None = None
    telegram_chat_id: str | None = None
    email_notifications_enabled: bool | None = None
    # How long before a lesson to send the "Скоро занятие" reminder (section 2.7) -
    # capped at a week (see notification_service.MAX_REMINDER_LEAD_MINUTES, which
    # send_upcoming_reminders' scan window is sized against).
    reminder_lead_minutes: int | None = Field(default=None, ge=1, le=7 * 24 * 60)
