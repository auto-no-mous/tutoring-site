import uuid

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import UTCDateTime
from app.schemas.tutor import TutorProfileUpdate


class AdminTutorUpdate(TutorProfileUpdate):
    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    patronymic: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    is_active: bool | None = None


class AdminStudentUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    patronymic: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    grade: int | None = Field(default=None, ge=1, le=11)
    timezone: str | None = None
    is_active: bool | None = None


class AdminPasswordReset(BaseModel):
    """Новый пароль, назначаемый админом. Ограничения те же, что при регистрации
    (schemas/auth.py::RegisterRequest), чтобы админ не мог завести пользователю
    пароль, который тот сам задать бы не смог."""

    new_password: str = Field(min_length=8, max_length=128)


class AdminGroupMemberAdd(BaseModel):
    student_id: uuid.UUID


class AdminGroupTutorReassign(BaseModel):
    tutor_id: uuid.UUID
    lesson_type_id: uuid.UUID


class AdminBookingCreate(BaseModel):
    tutor_id: uuid.UUID
    student_id: uuid.UUID | None = None
    lesson_type_id: uuid.UUID | None = None
    start_at: UTCDateTime
    end_at: UTCDateTime
    meeting_link: str | None = None
    notes: str | None = None


class AdminBookingReschedule(BaseModel):
    new_start_at: UTCDateTime
    duration_minutes: int | None = Field(default=None, gt=0)
