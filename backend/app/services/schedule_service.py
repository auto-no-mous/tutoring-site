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

    end_at_utc = start_at_utc + duration
    reserved_zones = await get_reserved_zones(
        db,
        tutor.id,
        start_at_utc - dt.timedelta(days=1),
        end_at_utc + dt.timedelta(days=1),
        tutor.break_between_lessons_minutes,
        exclude_booking_id=exclude_booking_id,
    )
    return not slot_conflicts(start_at_utc, end_at_utc, tutor.break_between_lessons_minutes, reserved_zones)


async def compute_day_slots(
    db: AsyncSession,
    tutor: TutorProfile,
    lesson_type: LessonType,
    target_date: dt.date,
    exclude_booking_id: uuid.UUID | None = None,
) -> list[SlotOut]:
    weekday = target_date.weekday()  # Monday=0 ... Sunday=6, matches WeeklyAvailability.weekday
    intervals = await get_weekly_intervals(db, tutor.id, weekday)
    if not intervals:
        return []

    step = dt.timedelta(minutes=tutor.slot_granularity_minutes)
    duration = dt.timedelta(minutes=lesson_type.duration_minutes)
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

    not_before = utcnow() + dt.timedelta(hours=tutor.min_lead_time_hours)

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


async def compute_available_dates(
    db: AsyncSession,
    tutor: TutorProfile,
    lesson_type: LessonType,
    date_from: dt.date,
    date_to: dt.date,
    exclude_booking_id: uuid.UUID | None = None,
) -> list[dt.date]:
    available_dates: list[dt.date] = []
    current = date_from
    while current <= date_to:
        slots = await compute_day_slots(db, tutor, lesson_type, current, exclude_booking_id=exclude_booking_id)
        if any(s.available for s in slots):
            available_dates.append(current)
        current += dt.timedelta(days=1)
    return available_dates
