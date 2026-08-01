import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UTCDateTime


class BookingCreate(BaseModel):
    tutor_id: uuid.UUID
    lesson_type_id: uuid.UUID
    start_at: UTCDateTime
    repeat_weekly: bool = False


class ManualBookingCreate(BaseModel):
    student_id: uuid.UUID | None = None
    lesson_type_id: uuid.UUID | None = None
    start_at: UTCDateTime
    end_at: UTCDateTime
    meeting_link: str | None = None
    notes: str | None = None
    repeat_weekly: bool = False


class BookingTutorUpdate(BaseModel):
    student_id: uuid.UUID | None = None
    start_at: UTCDateTime | None = None
    end_at: UTCDateTime | None = None
    meeting_link: str | None = None
    notes: str | None = None


class BookingCancelRequest(BaseModel):
    reason: str | None = None


class BookingRescheduleRequest(BaseModel):
    new_start_at: UTCDateTime


class BookingOutcomeUpdate(BaseModel):
    outcome: str


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tutor_id: uuid.UUID
    student_id: uuid.UUID | None
    lesson_type_id: uuid.UUID | None
    start_at: UTCDateTime
    end_at: UTCDateTime
    status: str
    is_manual_block: bool
    booked_by: str
    meeting_link: str | None
    notes: str | None
    recurring_series_id: uuid.UUID | None
    cancelled_by: str | None
    cancelled_at: UTCDateTime | None
    cancel_reason: str | None
    rescheduled_from_id: uuid.UUID | None
    outcome: str | None
    student_display_name: str | None = None
    # Whether the recurring series this booking belongs to is still generating future
    # occurrences - lets the frontend hide "stop recurring" once it's already stopped
    # (or show it at all only when recurring_series_id is set). None when no series.
    series_is_active: bool | None = None
    # Populated only on student-facing responses (student doesn't otherwise know which
    # lesson type / tutor a card refers to) - see api/v1/bookings.py::_to_booking_out.
    lesson_type_name: str | None = None
    # "Имя Отчество" only (no surname), per the student cabinet's card format. Admin's
    # listing (api/v1/admin.py::list_bookings) instead populates this with the full
    # display_name, since it has no single "counterpart" to omit the surname for.
    tutor_display_name: str | None = None


class BookingPageOut(BaseModel):
    items: list[BookingOut]
    total: int
    page: int
    page_size: int


class RecurringSeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tutor_id: uuid.UUID
    student_id: uuid.UUID
    lesson_type_id: uuid.UUID
    weekday: int
    start_time: dt.time
    is_active: bool


class RecurringSeriesDetailOut(RecurringSeriesOut):
    # Enrichment for display, e.g. in student settings (section 3.1 stop-recurring
    # flow) - "Понедельник, 09:00 - <lesson_type_name>. Репетитор <tutor_name>".
    lesson_type_name: str
    tutor_display_name: str
