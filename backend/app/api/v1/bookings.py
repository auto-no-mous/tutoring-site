import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.booking import RecurringSeries
from app.models.enums import BookingOutcome, UserRole
from app.schemas.booking import (
    BookingCancelRequest,
    BookingCreate,
    BookingOut,
    BookingOutcomeUpdate,
    BookingRescheduleRequest,
    BookingTutorUpdate,
    ManualBookingCreate,
    RecurringSeriesDetailOut,
    RecurringSeriesOut,
)
from app.schemas.schedule import SlotOut
from app.services import booking_service, schedule_service, tutor_service

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _require_student(user: CurrentUser) -> None:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только ученикам")


def _require_tutor(user: CurrentUser) -> None:
    if user.role != UserRole.TUTOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только репетиторам")


def _require_student_or_tutor(user: CurrentUser) -> None:
    if user.role not in (UserRole.STUDENT, UserRole.TUTOR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Недоступно")


def _to_booking_out(
    booking,
    student_name: str | None = None,
    series_is_active: bool | None = None,
    lesson_type_name: str | None = None,
    tutor_display_name: str | None = None,
) -> BookingOut:
    return BookingOut.model_validate(booking, from_attributes=True).model_copy(
        update={
            "student_display_name": student_name,
            "series_is_active": series_is_active,
            "lesson_type_name": lesson_type_name,
            "tutor_display_name": tutor_display_name,
        }
    )


async def _to_student_booking_out(db: DbSession, booking) -> BookingOut:
    """Student-facing single-booking response, enriched with the lesson type name and
    the tutor's "Имя Отчество" (section 3.1/3.2 card format)."""
    series_map = await booking_service.get_series_active_map(db, [booking.recurring_series_id])
    lesson_type_names = await booking_service.get_lesson_type_names(db, [booking.lesson_type_id])
    tutor_names = await booking_service.get_tutor_name_patronymic_map(db, [booking.tutor_id])
    return _to_booking_out(
        booking,
        series_is_active=series_map.get(booking.recurring_series_id),
        lesson_type_name=lesson_type_names.get(booking.lesson_type_id),
        tutor_display_name=tutor_names.get(booking.tutor_id),
    )


async def _to_role_aware_booking_out(db: DbSession, booking, current_user: CurrentUser) -> BookingOut:
    """Cancel/reschedule are now available to both roles - render the response shape
    each side's UI actually expects (see the two builders above)."""
    if current_user.role == UserRole.TUTOR:
        names = await booking_service.get_student_names(db, [booking.student_id] if booking.student_id else [])
        series_map = await booking_service.get_series_active_map(db, [booking.recurring_series_id])
        return _to_booking_out(
            booking,
            names.get(booking.student_id) if booking.student_id else None,
            series_map.get(booking.recurring_series_id),
        )
    return await _to_student_booking_out(db, booking)


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(payload: BookingCreate, current_user: CurrentUser, db: DbSession) -> BookingOut:
    _require_student(current_user)
    booking = await booking_service.create_student_booking(
        db, current_user, payload.tutor_id, payload.lesson_type_id, payload.start_at, payload.repeat_weekly
    )
    return await _to_student_booking_out(db, booking)


@router.get("/me", response_model=list[BookingOut])
async def list_my_bookings(current_user: CurrentUser, db: DbSession) -> list[BookingOut]:
    _require_student(current_user)
    rows = await booking_service.list_bookings_for_student(db, current_user.id)
    series_map = await booking_service.get_series_active_map(db, [r.recurring_series_id for r in rows])
    lesson_type_names = await booking_service.get_lesson_type_names(db, [r.lesson_type_id for r in rows])
    tutor_names = await booking_service.get_tutor_name_patronymic_map(db, [r.tutor_id for r in rows])
    return [
        _to_booking_out(
            r,
            series_is_active=series_map.get(r.recurring_series_id),
            lesson_type_name=lesson_type_names.get(r.lesson_type_id),
            tutor_display_name=tutor_names.get(r.tutor_id),
        )
        for r in rows
    ]


@router.post("/{booking_id}/cancel", response_model=BookingOut)
async def cancel_booking(
    booking_id: uuid.UUID, payload: BookingCancelRequest, current_user: CurrentUser, db: DbSession
) -> BookingOut:
    _require_student_or_tutor(current_user)
    booking = await booking_service.get_booking_or_404(db, booking_id)
    booking = await booking_service.cancel_booking(db, booking, current_user, payload.reason)
    return await _to_role_aware_booking_out(db, booking, current_user)


@router.get("/{booking_id}/reschedule/dates", response_model=list[dt.date])
async def get_reschedule_dates(
    booking_id: uuid.UUID, date_from: dt.date, date_to: dt.date, current_user: CurrentUser, db: DbSession
) -> list[dt.date]:
    _require_student_or_tutor(current_user)
    if (date_to - date_from).days > 60:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Слишком большой диапазон дат")
    booking = await booking_service.get_booking_or_404(db, booking_id)
    tutor, lesson_type = await booking_service.get_reschedule_context(db, booking, current_user)
    return await schedule_service.compute_available_dates(
        db, tutor, lesson_type, date_from, date_to, exclude_booking_id=booking.id
    )


@router.get("/{booking_id}/reschedule/slots", response_model=list[SlotOut])
async def get_reschedule_slots(
    booking_id: uuid.UUID, date: dt.date, current_user: CurrentUser, db: DbSession
) -> list[SlotOut]:
    _require_student_or_tutor(current_user)
    booking = await booking_service.get_booking_or_404(db, booking_id)
    tutor, lesson_type = await booking_service.get_reschedule_context(db, booking, current_user)
    return await schedule_service.compute_day_slots(db, tutor, lesson_type, date, exclude_booking_id=booking.id)


@router.post("/{booking_id}/reschedule", response_model=BookingOut)
async def reschedule_booking(
    booking_id: uuid.UUID, payload: BookingRescheduleRequest, current_user: CurrentUser, db: DbSession
) -> BookingOut:
    _require_student_or_tutor(current_user)
    booking = await booking_service.get_booking_or_404(db, booking_id)
    new_booking = await booking_service.reschedule_booking(db, booking, current_user, payload.new_start_at)
    return await _to_role_aware_booking_out(db, new_booking, current_user)


@router.get("/series/me", response_model=list[RecurringSeriesDetailOut])
async def list_my_recurring_series(current_user: CurrentUser, db: DbSession) -> list[RecurringSeriesDetailOut]:
    _require_student(current_user)
    rows = await booking_service.list_active_series_for_student(db, current_user.id)
    return [RecurringSeriesDetailOut(**row) for row in rows]


@router.post("/series/{series_id}/stop", response_model=RecurringSeriesOut)
async def stop_recurring_series(series_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> RecurringSeriesOut:
    _require_student(current_user)
    series = await db.get(RecurringSeries, series_id)
    if series is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Серия занятий не найдена")
    series = await booking_service.stop_recurring_series(db, series, current_user)
    return RecurringSeriesOut.model_validate(series, from_attributes=True)


@router.post("/manual", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_manual_booking(payload: ManualBookingCreate, current_user: CurrentUser, db: DbSession) -> BookingOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    booking = await booking_service.create_manual_booking(db, profile, payload)
    names = await booking_service.get_student_names(db, [booking.student_id] if booking.student_id else [])
    series_map = await booking_service.get_series_active_map(db, [booking.recurring_series_id])
    return _to_booking_out(
        booking,
        names.get(booking.student_id) if booking.student_id else None,
        series_map.get(booking.recurring_series_id),
    )


@router.get("/tutor/me", response_model=list[BookingOut])
async def list_my_tutor_bookings(current_user: CurrentUser, db: DbSession) -> list[BookingOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    rows = await booking_service.list_bookings_for_tutor(db, profile.id)
    names = await booking_service.get_student_names(db, [r.student_id for r in rows if r.student_id])
    series_map = await booking_service.get_series_active_map(db, [r.recurring_series_id for r in rows])
    return [
        _to_booking_out(r, names.get(r.student_id) if r.student_id else None, series_map.get(r.recurring_series_id))
        for r in rows
    ]


@router.patch("/{booking_id}", response_model=BookingOut)
async def update_booking(
    booking_id: uuid.UUID, payload: BookingTutorUpdate, current_user: CurrentUser, db: DbSession
) -> BookingOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    booking = await booking_service.get_booking_or_404(db, booking_id)
    if booking.tutor_id != profile.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше занятие")
    booking = await booking_service.update_booking_by_tutor(db, booking, payload)
    names = await booking_service.get_student_names(db, [booking.student_id] if booking.student_id else [])
    series_map = await booking_service.get_series_active_map(db, [booking.recurring_series_id])
    return _to_booking_out(
        booking,
        names.get(booking.student_id) if booking.student_id else None,
        series_map.get(booking.recurring_series_id),
    )


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking(booking_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    booking = await booking_service.get_booking_or_404(db, booking_id)
    if booking.tutor_id != profile.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше занятие")
    await booking_service.delete_booking(db, booking)


@router.patch("/{booking_id}/outcome", response_model=BookingOut)
async def set_booking_outcome(
    booking_id: uuid.UUID, payload: BookingOutcomeUpdate, current_user: CurrentUser, db: DbSession
) -> BookingOut:
    _require_tutor(current_user)
    if payload.outcome not in (o.value for o in BookingOutcome):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Некорректный статус занятия")
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    booking = await booking_service.get_booking_or_404(db, booking_id)
    booking = await booking_service.set_booking_outcome(db, profile, booking, payload.outcome)
    names = await booking_service.get_student_names(db, [booking.student_id] if booking.student_id else [])
    series_map = await booking_service.get_series_active_map(db, [booking.recurring_series_id])
    return _to_booking_out(
        booking,
        names.get(booking.student_id) if booking.student_id else None,
        series_map.get(booking.recurring_series_id),
    )
