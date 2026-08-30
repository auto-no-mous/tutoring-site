import datetime as dt
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import BookingStatus, GroupOccurrenceStatus
from app.models.group import Group, GroupOccurrence
from app.models.lesson_type import LessonType
from app.models.schedule import WeeklyAvailability
from app.models.tutor import TutorProfile
from app.schemas.schedule import SlotOut
from app.utils.time import ensure_aware, utcnow

# Canonical timezone for a tutor's own schedule (weekly availability, recurring series,
# group schedule) - see project_description.md sections 2.3 and 6: the tutor cabinet
# always shows MSK regardless of the tutor's actual location.
MSK = ZoneInfo("Europe/Moscow")


def _merge_intervals(intervals: list[tuple[dt.time, dt.time]]) -> list[tuple[dt.time, dt.time]]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda iv: iv[0])
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _combine_msk(target_date: dt.date, t: dt.time) -> dt.datetime:
    return dt.datetime.combine(target_date, t, tzinfo=MSK)


async def get_weekly_intervals(
    db: AsyncSession, tutor_id: uuid.UUID, weekday: int
) -> list[tuple[dt.time, dt.time]]:
    result = await db.execute(
        select(WeeklyAvailability).where(
            WeeklyAvailability.tutor_id == tutor_id, WeeklyAvailability.weekday == weekday
        )
    )
    rows = result.scalars().all()
    return _merge_intervals([(r.start_time, r.end_time) for r in rows])


async def get_reserved_zones(
    db: AsyncSession,
    tutor_id: uuid.UUID,
    window_start_utc: dt.datetime,
    window_end_utc: dt.datetime,
    break_minutes: int,
    exclude_booking_id: uuid.UUID | None = None,
) -> list[tuple[dt.datetime, dt.datetime]]:
    """Reserved zones = [start, end + break) for active individual bookings (incl.
    manual blocks) and scheduled group occurrences overlapping the window."""
    booking_query = select(Booking).where(
        Booking.tutor_id == tutor_id,
        Booking.status == BookingStatus.SCHEDULED.value,
        Booking.start_at < window_end_utc,
        Booking.end_at > window_start_utc,
    )
    if exclude_booking_id is not None:
        booking_query = booking_query.where(Booking.id != exclude_booking_id)

    booking_result = await db.execute(booking_query)
    zones = [
        (ensure_aware(b.start_at), ensure_aware(b.end_at) + dt.timedelta(minutes=break_minutes))
        for b in booking_result.scalars().all()
    ]

    occurrence_result = await db.execute(
        select(GroupOccurrence)
        .join(Group, Group.id == GroupOccurrence.group_id)
        .where(
            Group.tutor_id == tutor_id,
            GroupOccurrence.status == GroupOccurrenceStatus.SCHEDULED.value,
            GroupOccurrence.start_at < window_end_utc,
            GroupOccurrence.end_at > window_start_utc,
        )
    )
    zones += [
        (ensure_aware(o.start_at), ensure_aware(o.end_at) + dt.timedelta(minutes=break_minutes))
        for o in occurrence_result.scalars().all()
    ]
    return zones


def slot_conflicts(
    candidate_start: dt.datetime,
    candidate_end: dt.datetime,
    break_minutes: int,
    reserved_zones: list[tuple[dt.datetime, dt.datetime]],
) -> bool:
    """Symmetric overlap test: a candidate and an existing booking conflict unless
    there's at least `break_minutes` of gap between whichever ends first and the one
    that starts later (see project_description.md section 2.3 for the worked example)."""
    candidate_zone_end = candidate_end + dt.timedelta(minutes=break_minutes)
    for zone_start, zone_end in reserved_zones:
        if candidate_start < zone_end and candidate_zone_end > zone_start:
            return True
    return False


async def is_slot_available(
    db: AsyncSession,
    tutor: TutorProfile,
    lesson_type: LessonType,
    start_at_utc: dt.datetime,
    exclude_booking_id: uuid.UUID | None = None,
) -> bool:
    """Single-slot check used when actually booking/rescheduling (as opposed to
    compute_day_slots, which renders a whole day's grid for the UI)."""
    start_msk = start_at_utc.astimezone(MSK)
    target_date = start_msk.date()
    duration = dt.timedelta(minutes=lesson_type.duration_minutes)
    end_msk = start_msk + duration

    intervals = await get_weekly_intervals(db, tutor.id, target_date.weekday())
    fits_interval = any(
        _combine_msk(target_date, iv_start) <= start_msk and end_msk <= _combine_msk(target_date, iv_end)
        for iv_start, iv_end in intervals
    )
    if not fits_interval:
        return False

    not_before = utcnow() + dt.timedelta(hours=tutor.min_lead_time_hours)
    if start_at_utc < not_before:
        return False

    return not await has_conflict(db, tutor, lesson_type, start_at_utc, exclude_booking_id)


async def has_conflict(
    db: AsyncSession,
    tutor: TutorProfile,
    lesson_type: LessonType,
    start_at_utc: dt.datetime,
    exclude_booking_id: uuid.UUID | None = None,
) -> bool:
    """Только пересечение с уже занятым временем, без оглядки на недельное расписание
    и минимальный запас по времени.

    Отдельно от is_slot_available, потому что репетитор - хозяин своей сетки: он может
    поставить занятие вне расписания (ручная запись это уже позволяет), но поставить
    два занятия на одно время не может никто.
    """
    end_at_utc = start_at_utc + dt.timedelta(minutes=lesson_type.duration_minutes)
    reserved_zones = await get_reserved_zones(
        db,
        tutor.id,
        start_at_utc - dt.timedelta(days=1),
        end_at_utc + dt.timedelta(days=1),
        tutor.break_between_lessons_minutes,
        exclude_booking_id=exclude_booking_id,
    )
    return slot_conflicts(start_at_utc, end_at_utc, tutor.break_between_lessons_minutes, reserved_zones)


async def compute_day_slots_by_duration(
    db: AsyncSession,
    tutor: TutorProfile,
    duration_minutes: int,
    target_date: dt.date,
    exclude_booking_id: uuid.UUID | None = None,
    ignore_lead_time: bool = False,
) -> list[SlotOut]:
    """Core slot-grid computation, keyed off a raw duration rather than a LessonType
    row - lets the admin reschedule browser work for manual bookings too (see
    compute_day_slots below and booking_service.get_admin_reschedule_context).
    `ignore_lead_time` skips the tutor's min_lead_time_hours cushion, consistent with
    admin_reschedule_booking having no policy limits."""
    weekday = target_date.weekday()  # Monday=0 ... Sunday=6, matches WeeklyAvailability.weekday
    intervals = await get_weekly_intervals(db, tutor.id, weekday)
    if not intervals:
        return []

    step = dt.timedelta(minutes=tutor.slot_granularity_minutes)
    duration = dt.timedelta(minutes=duration_minutes)
    break_minutes = tutor.break_between_lessons_minutes

    day_start_utc = _combine_msk(target_date, dt.time(0, 0)).astimezone(dt.timezone.utc)
    day_end_utc = day_start_utc + dt.timedelta(days=1)
    # Widen the reservation lookup window so bookings whose break trails in/out of the
    # calendar day are still accounted for.
    reserved_zones = await get_reserved_zones(
        db,
        tutor.id,
        day_start_utc - dt.timedelta(days=1),
        day_end_utc + dt.timedelta(days=1),
        break_minutes,
        exclude_booking_id=exclude_booking_id,
    )

    not_before = utcnow() if ignore_lead_time else utcnow() + dt.timedelta(hours=tutor.min_lead_time_hours)

    slots: list[SlotOut] = []
    for interval_start, interval_end in intervals:
        mark = _combine_msk(target_date, interval_start)
        interval_end_dt = _combine_msk(target_date, interval_end)
        while mark < interval_end_dt:
            mark_utc = mark.astimezone(dt.timezone.utc)
            mark_end_utc = mark_utc + duration

            fits_interval = mark + duration <= interval_end_dt
            not_too_soon = mark_utc >= not_before
            conflict = slot_conflicts(mark_utc, mark_end_utc, break_minutes, reserved_zones)

            slots.append(
                SlotOut(
                    start_at=mark_utc,
                    end_at=mark_end_utc,
                    available=fits_interval and not_too_soon and not conflict,
                )
            )
            mark += step

    return slots


# На сколько сетка репетитора шире его рабочих часов - чтобы перенести занятие чуть
# раньше или позже обычного, не заводя ради этого новый интервал в расписании.
TUTOR_GRID_PADDING_HOURS = 2
# Запасная полоса, если недельное расписание ещё вовсе не заполнено.
TUTOR_GRID_FALLBACK = (dt.time(8, 0), dt.time(22, 0))


async def get_tutor_grid_bounds(db: AsyncSession, tutor_id: uuid.UUID) -> tuple[dt.time, dt.time]:
    """Границы сетки времени, которую видит сам репетитор при переносе занятия.

    Берём самый ранний и самый поздний час из всего недельного расписания и
    расширяем на TUTOR_GRID_PADDING_HOURS в обе стороны. Одинаково для всех дней,
    включая те, где репетитор обычно не работает: перенос для него не ограничен
    расписанием, и сетка нужна как удобная рамка, а не как правило.
    """
    result = await db.execute(select(WeeklyAvailability).where(WeeklyAvailability.tutor_id == tutor_id))
    rows = result.scalars().all()
    if not rows:
        return TUTOR_GRID_FALLBACK

    earliest = min(r.start_time for r in rows)
    latest = max(r.end_time for r in rows)
    start_hour = max(0, earliest.hour - TUTOR_GRID_PADDING_HOURS)
    # Округляем конец вверх до часа, прежде чем добавлять запас, иначе окно до 19:30
    # дало бы сетку до 21:30 и половинчатый последний час.
    end_hour = latest.hour + (1 if latest.minute else 0) + TUTOR_GRID_PADDING_HOURS
    if end_hour >= 24:
        return dt.time(start_hour, 0), dt.time(23, 59)
    return dt.time(start_hour, 0), dt.time(end_hour, 0)


async def compute_tutor_day_slots(
    db: AsyncSession,
    tutor: TutorProfile,
    duration_minutes: int,
    target_date: dt.date,
    exclude_booking_id: uuid.UUID | None = None,
) -> list[SlotOut]:
    """Сетка слотов для самого репетитора: показываем весь день целиком, ничего не
    отсеивая.

    Отличие от compute_day_slots_by_duration принципиальное. Там сетка строится по
    недельному расписанию и отсеивает всё, что занято, слишком скоро или вне рабочих
    часов - это правила для ученика. Репетитору же переносить можно куда угодно,
    включая прошлое и наложение на другое занятие, поэтому здесь каждый слот
    выбираем (available=True), а занятость отдаём отдельным признаком busy, чтобы
    интерфейс мог её подсветить.
    """
    grid_start, grid_end = await get_tutor_grid_bounds(db, tutor.id)
    step = dt.timedelta(minutes=tutor.slot_granularity_minutes)
    duration = dt.timedelta(minutes=duration_minutes)
    break_minutes = tutor.break_between_lessons_minutes

    day_start_utc = _combine_msk(target_date, dt.time(0, 0)).astimezone(dt.timezone.utc)
    reserved_zones = await get_reserved_zones(
        db,
        tutor.id,
        day_start_utc - dt.timedelta(days=1),
        day_start_utc + dt.timedelta(days=2),
        break_minutes,
        exclude_booking_id=exclude_booking_id,
    )

    slots: list[SlotOut] = []
    mark = _combine_msk(target_date, grid_start)
    grid_end_dt = _combine_msk(target_date, grid_end)
    while mark <= grid_end_dt:
        mark_utc = mark.astimezone(dt.timezone.utc)
        slots.append(
            SlotOut(
                start_at=mark_utc,
                end_at=mark_utc + duration,
                available=True,
                busy=slot_conflicts(mark_utc, mark_utc + duration, break_minutes, reserved_zones),
            )
        )
        mark += step
    return slots


async def compute_day_slots(
    db: AsyncSession,
    tutor: TutorProfile,
    lesson_type: LessonType,
    target_date: dt.date,
    exclude_booking_id: uuid.UUID | None = None,
) -> list[SlotOut]:
    return await compute_day_slots_by_duration(
        db, tutor, lesson_type.duration_minutes, target_date, exclude_booking_id=exclude_booking_id
    )


async def compute_available_dates_by_duration(
    db: AsyncSession,
    tutor: TutorProfile,
    duration_minutes: int,
    date_from: dt.date,
    date_to: dt.date,
    exclude_booking_id: uuid.UUID | None = None,
    ignore_lead_time: bool = False,
) -> list[dt.date]:
    available_dates: list[dt.date] = []
    current = date_from
    while current <= date_to:
        slots = await compute_day_slots_by_duration(
            db, tutor, duration_minutes, current, exclude_booking_id=exclude_booking_id, ignore_lead_time=ignore_lead_time
        )
        if any(s.available for s in slots):
            available_dates.append(current)
        current += dt.timedelta(days=1)
    return available_dates


async def compute_available_dates(
    db: AsyncSession,
    tutor: TutorProfile,
    lesson_type: LessonType,
    date_from: dt.date,
    date_to: dt.date,
    exclude_booking_id: uuid.UUID | None = None,
) -> list[dt.date]:
    return await compute_available_dates_by_duration(
        db, tutor, lesson_type.duration_minutes, date_from, date_to, exclude_booking_id=exclude_booking_id
    )
