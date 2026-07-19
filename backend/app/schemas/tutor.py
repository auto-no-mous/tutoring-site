import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.subject import TutorSubjectOut


class TutorScheduleSettings(BaseModel):
    slot_granularity_minutes: int
    break_between_lessons_minutes: int = Field(ge=0)
    min_lead_time_hours: int = Field(ge=0)
    cancel_min_hours_before: int = Field(ge=0)
    cancel_max_per_month: int = Field(ge=0)
    reschedule_min_hours_before: int = Field(ge=0)
    reschedule_max_per_month: int = Field(ge=0)


class TutorProfileUpdate(BaseModel):
    about: str | None = None
    achievements: str | None = None
    is_hidden: bool | None = None
    slot_granularity_minutes: int | None = None
    break_between_lessons_minutes: int | None = Field(default=None, ge=0)
    min_lead_time_hours: int | None = Field(default=None, ge=0)
    cancel_min_hours_before: int | None = Field(default=None, ge=0)
    cancel_max_per_month: int | None = Field(default=None, ge=0)
    reschedule_min_hours_before: int | None = Field(default=None, ge=0)
    reschedule_max_per_month: int | None = Field(default=None, ge=0)


class TutorProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    photo_url: str | None
    about: str
    achievements: str
    is_hidden: bool
    slot_granularity_minutes: int
    break_between_lessons_minutes: int
    min_lead_time_hours: int
    cancel_min_hours_before: int
    cancel_max_per_month: int
    reschedule_min_hours_before: int
    reschedule_max_per_month: int
    display_name: str | None = None
    is_active: bool | None = None


class TutorCatalogItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    # "Имя Отчество" only (no surname) - the format used on catalog cards.
    name_patronymic: str
    photo_url: str | None
    subjects: list[str] = Field(default_factory=list)
    # Cheapest individual lesson type, normalized to a per-hour rate
    # (price / duration_minutes * 60) so tutors with different lesson lengths are
    # comparable - see tutor_service.search_catalog.
    hourly_price: float | None = None
    avg_rating: float | None = None
    reviews_count: int = 0


class TutorPublicProfile(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    photo_url: str | None
    about: str
    achievements: str
    subjects: list[TutorSubjectOut] = Field(default_factory=list)
    avg_rating: float | None = None
    reviews_count: int = 0
