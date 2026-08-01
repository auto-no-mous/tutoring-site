import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UTCDateTime
from app.schemas.subject import TutorSubjectOut

# Lowercase letters/digits, hyphens allowed in the middle only, 3-64 chars total -
# used for the tutor's optional public-profile nickname (it-tutor.pro/tutors/<slug>).
SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{1,62}[a-z0-9])?$"


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
    is_hidden: bool | None = None
    slug: str | None = Field(default=None, pattern=SLUG_PATTERN)
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
    is_hidden: bool
    slug: str | None = None
    slot_granularity_minutes: int
    break_between_lessons_minutes: int
    min_lead_time_hours: int
    cancel_min_hours_before: int
    cancel_max_per_month: int
    reschedule_min_hours_before: int
    reschedule_max_per_month: int
    display_name: str | None = None
    is_active: bool | None = None
    # Populated only where the caller already has the linked User at hand (own
    # profile, admin) - see api/v1/tutors.py::_to_profile_out /
    # api/v1/admin.py::_to_profile_out. Lets the edit form prefill the split name
    # fields and email instead of only showing the denormalized display_name.
    first_name: str | None = None
    last_name: str | None = None
    patronymic: str | None = None
    email: str | None = None
    # Populated only by the admin tutor listing (see api/v1/admin.py::list_tutors) -
    # lets the admin bookings-tab filters narrow bookings down by the tutor's subjects
    # and directions without a separate lookup.
    subjects: list[TutorSubjectOut] = Field(default_factory=list)


class TutorCatalogItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    # "Имя Отчество" only (no surname) - the format used on catalog cards.
    name_patronymic: str
    photo_url: str | None
    slug: str | None = None
    subjects: list[str] = Field(default_factory=list)
    # Cheapest individual lesson type, normalized to a per-hour rate
    # (price / duration_minutes * 60) so tutors with different lesson lengths are
    # comparable - see tutor_service.search_catalog.
    hourly_price: float | None = None
    avg_rating: float | None = None
    reviews_count: int = 0


class TutorCatalogPageOut(BaseModel):
    items: list[TutorCatalogItem]
    total: int
    page: int
    page_size: int


class TutorPublicProfile(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    photo_url: str | None
    about: str
    subjects: list[TutorSubjectOut] = Field(default_factory=list)
    avg_rating: float | None = None
    reviews_count: int = 0


class UploadedImageOut(BaseModel):
    """A single uploaded image's URL, e.g. for insertion into the "about" rich text
    field - see api/v1/tutors.py::upload_about_image."""

    url: str


class TutorStudentOut(BaseModel):
    """Entry in the tutor's homework-assignment student picker (see
    booking_service.list_students_for_tutor), sorted by most recent lesson first."""

    id: uuid.UUID
    first_name: str
    last_name: str
    grade: int | None
    last_lesson_at: UTCDateTime | None
