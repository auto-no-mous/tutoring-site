import uuid

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import UTCDateTime
from app.schemas.tutor import TutorProfileUpdate


class AdminTutorUpdate(TutorProfileUpdate):
    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    patronymic: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class AdminStudentUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    patronymic: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    is_active: bool | None = None


class AdminBookingCreate(BaseModel):
    tutor_id: uuid.UUID
    student_id: uuid.UUID | None = None
    lesson_type_id: uuid.UUID | None = None
    start_at: UTCDateTime
    end_at: UTCDateTime
    meeting_link: str | None = None
    notes: str | None = None
