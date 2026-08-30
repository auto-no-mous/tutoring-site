import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UTCDateTime

# Потолок разовой длительности занятия, которую репетитор задаёт руками при
# переносе. Восемь часов - заведомо больше любого осмысленного занятия и при этом
# защищает от опечатки вроде 6000 минут, которая перекрыла бы весь календарь.
MAX_LESSON_DURATION_MINUTES = 8 * 60


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
    # When true and meeting_link is being set, also applies it to every other of this
    # tutor's scheduled bookings with the same student (see
    # booking_service.update_booking_by_tutor) - powers the "Постоянная ссылка на
    # занятие с этим учеником" checkbox in components/MeetingLinkModal.vue. Not a real
    # Booking column, just a one-shot instruction for this request.
    apply_link_to_student: bool = False


class BookingCancelRequest(BaseModel):
    reason: str | None = None


class BookingRescheduleRequest(BaseModel):
    new_start_at: UTCDateTime
    # Оба поля - только для репетитора: перенося занятие, он может заодно сменить его
    # тип или разово задать другую длительность (см. booking_service.reschedule_booking,
    # который отклонит их у ученика). None означает "оставить как было".
    lesson_type_id: uuid.UUID | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=MAX_LESSON_DURATION_MINUTES)


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
    # Populated for both roles (see api/v1/bookings.py::_to_booking_out) so every card
    # can show what kind of lesson it is - duration is derivable from start_at/end_at
    # on the frontend, so only name/format need a round trip.
    lesson_type_name: str | None = None
    lesson_type_format: str | None = None
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


class TutorRecurringSeriesOut(RecurringSeriesOut):
    """То же для блока «Ученики» в статистике: там серия подписывается учеником, а не
    репетитором - он и так знает, чьи это занятия."""

    lesson_type_name: str
    student_display_name: str
